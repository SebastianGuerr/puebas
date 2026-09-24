# -*- coding: utf-8 -*-
"""
La tabla para analisis: una fila por nota y nada que lleve a la persona.

    python -m NLP.nube.tabla --exportar --muestra 300    N notas repartidas por la tabla
    python -m NLP.nube.tabla --exportar                  todas las notas con texto
          [--forzar]                                     aparta el mapa anterior y rehace
    python -m NLP.nube.tabla --auditar                   revisa el CSV; si falla, lo borra
    python -m NLP.nube.tabla --estado                    que hay en NLP/salidas/tabla/

LO QUE SALE: notas_triage.csv.gz, seis columnas y nada mas
    id            16 hex de secrets. No es un hash del OID: un hash se deshace
                  recalculandolo para cada OID candidato
    fecha         el DIA. CAST(HCTFECTRI AS DATE) se hace en SQL Server: la hora
                  no llega ni a la memoria de este proceso
    nivel         HCCODIGO del nivel de urgencia. Los niveles con menos de
                  MINIMO_NIVEL notas en toda la tabla salen como 'otro'
    nivel_nombre  su HCDESCRIP, con la misma regla
    edad_banda    la banda la calcula SQL Server con el CASE de extraccion/, el
                  mismo de salidas/triage_edad.parquet: la edad exacta tampoco
                  llega a Python
    nota          HCTMOTCON con lo identificable BORRADO, no marcado, y en una
                  sola linea. Lo borrado es lo que tapa enmascarar.py

LO QUE SE QUEDA EN ESTE EQUIPO
    mapa_local.parquet  id -> OID. Lo unico que devuelve una fila a su triage
    lote.json           huella del CSV y conteos
    auditoria.json      solo conteos

ORDEN DEL CSV
    Por dia y, dentro del dia, por id. Como el id es aleatorio, dentro del dia
    el orden tambien lo es. Por OID no: el OID crece con la hora, y la posicion
    de la fila diria a que hora llego cada paciente.

El porque de cada decision y sus limites: NLP/docs/TABLA.md.
"""

import argparse
import json
import math
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from NLP import rutas
from NLP.nube import MARCAS
from NLP.nube import auditar as aud
from NLP.nube import enmascarar as em
from NLP.nube import exportar

CARPETA = rutas.SALIDAS / "tabla"
ARCHIVO = "notas_triage.csv.gz"   # sale
MAPA = "mapa_local.parquet"       # NUNCA sale: id -> OID
LOTE = "lote.json"                # NUNCA sale: huella y conteos
AUDITORIA = "auditoria.json"      # NUNCA sale: solo conteos

COLUMNAS = ["id", "fecha", "nivel", "nivel_nombre", "edad_banda", "nota"]

TABLA_NIVEL = "DIM_HCNCLAURGTR"
OTRO = "otro"
SIN_EDAD = "sin edad"

# Un nivel con menos notas que esto en toda la tabla sale como 'otro'. Es la
# supresion de celdas pequenas de cualquier boletin: 'MUERTO' tiene 285 casos
# en seis anos, y 'dia + murio en urgencias + lo que paso' se cruza con una
# noticia. Juntos, los niveles por debajo suman menos del 0,2 % de los triages.
MINIMO_NIVEL = 100

# Contar terminos clinicos cuesta 12 ms por nota (medido el 2026-09-24): con
# todas serian 40 minutos para una comprobacion de calidad, no de privacidad.
MUESTRA_TERMINOS = 2000

_MARCA = re.compile("|".join(re.escape(m) for m in MARCAS))
_DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
_ID = re.compile(r"[0-9a-f]{16}")

# Lo que tapa enmascarar() y, aparte, lo que quita la red de fechas.
TIPOS = tuple(em.TIPOS) + ("fecha_red",)

huella = exportar.huella


def bandas_de_edad():
    """Las etiquetas que produce _caso_edad() de extraccion/__main__.py."""
    from extraccion import BANDAS_EDAD
    return frozenset([f"{d}-{h if h < 200 else '+'}" for d, h in BANDAS_EDAD] + [SIN_EDAD])


# ==========================================================
# BORRAR (sin base de datos: se prueba con datos sinteticos)
# ==========================================================

def ordenar(texto):
    """Una sola linea, sin el hueco que deja lo borrado."""
    t = re.sub(r"\(\s*\)|\[\s*\]", " ", texto)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:)])", r"\1", t)
    t = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", t)
    return t.strip(" ,;:-")


def _red_de_fechas(texto):
    """
    (texto, cuantos tramos quito): borra lo que la auditoria llama fecha completa.

    enmascarar() no toca una fecha pegada a un guion a proposito, para no partir
    series de signos como '120/80-...'. La auditoria si la atrapa, y en la
    corrida completa del 2026-09-24 eso tumbo el CSV por 3 de 95.424 notas: una
    fecha real '(fx. -dd/mm/aaaa)' y dos series con forma de fecha. Aqui se borra
    igual; perder la cola de una serie de signos en 2 notas vale menos que una
    fecha. La copia plana tiene la misma longitud que el texto, asi que los
    tramos se cortan del original.
    """
    tramos = []
    plano = aud._plano(texto)
    for patron in (aud._FECHA_NUM, aud._FECHA_ISO, aud._FECHA_TEXTO):
        tramos += [(m.start(), m.end()) for m in patron.finditer(plano)]
    for inicio, fin in sorted(tramos, reverse=True):
        texto = texto[:inicio] + " " + texto[fin:]
    return texto, len(tramos)


def borrar(texto, identidad=None, nombres=None):
    """
    (nota sin lo identificable, conteo por tipo).

    Tapa con enmascarar() y quita la marca. La marca pasa a ser un espacio y
    nunca nada: 'hace 3 [FECHA] 12 semanas' no puede acabar en '312 semanas'.
    Despues pasa la red de fechas; lo que quita va en conteo['fecha_red'].
    """
    enmascarado, conteo = em.enmascarar("" if texto is None else str(texto), identidad, nombres)
    limpio, red = _red_de_fechas(_MARCA.sub(" ", enmascarado))
    return ordenar(limpio), {**conteo, "fecha_red": red}


def revisar_nota(nota, identidad):
    """Las banderas de UNA nota ya borrada (lista vacia si esta limpia)."""
    nota = "" if nota is None else str(nota)
    banderas = []
    if _MARCA.search(nota):
        banderas.append("marca_sin_borrar")
    if em.restos_de_identidad(nota, identidad or em.Identidad()):
        banderas.append("resto_de_identidad")
    plano = aud._plano(nota)
    if aud._CIFRAS.search(plano):
        banderas.append("cifras_5_o_mas")
    if aud._FECHA_NUM.search(plano) or aud._FECHA_ISO.search(plano) or aud._FECHA_TEXTO.search(plano):
        banderas.append("fecha_completa")
    if aud._TELEFONO.search(plano) or aud._MILES.search(plano):
        banderas.append("telefono_o_documento")
    if aud._CORREO.search(plano):
        banderas.append("correo")
    if aud._URL.search(plano):
        banderas.append("url")
    return banderas


def _texto(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ""
    return str(valor).strip()


def _dia(valor):
    return pd.Timestamp(valor).strftime("%Y-%m-%d")


# ==========================================================
# ARMAR
# ==========================================================

def armar(notas, nombres=None, carpeta=CARPETA, niveles_raros=frozenset(), informar=True):
    """
    notas: DataFrame con OID, fecha, nivel, nivel_nombre, edad_banda, HCTMOTCON
    y las cinco columnas de identidad.

    Escribe el CSV, mapa_local.parquet y lote.json en `carpeta`. Devuelve
    {id: Identidad} para auditar con la identidad todavia en memoria.
    """
    from NLP import glosario

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    niveles_raros = frozenset(niveles_raros)
    filas = notas.to_dict("records")
    ids = exportar.ids_aleatorios(len(filas))

    salida, mapa, identidades, borradas = [], [], {}, []
    por_tipo, nombres_raros, inicio = Counter(), set(), time.time()
    for posicion, (fila, id_) in enumerate(zip(filas, ids), 1):
        identidad = em.Identidad.de_fila(fila)
        nota, conteo = borrar(fila[exportar.COLUMNA], identidad, nombres)
        por_tipo.update(t for t in TIPOS if conteo.get(t, 0))
        nivel, nombre = _texto(fila.get("nivel")), _texto(fila.get("nivel_nombre"))
        if nivel in niveles_raros:
            nombres_raros.add(nombre)
            nivel = nombre = OTRO
        salida.append({"id": id_, "fecha": _dia(fila["fecha"]), "nivel": nivel,
                       "nivel_nombre": nombre,
                       "edad_banda": _texto(fila.get("edad_banda")) or SIN_EDAD, "nota": nota})
        mapa.append({"id": id_, "OID": int(fila[exportar.LLAVE])})
        identidades[id_] = identidad
        borradas.append(nota)
        if informar and (posicion % 5000 == 0 or posicion == len(filas)):
            print(f"\r  {posicion:,}/{len(filas):,} notas borradas   "
                  f"{posicion / max(time.time() - inicio, 1e-9):6.0f} notas/s", end="", flush=True)
    if informar:
        print()

    datos = pd.DataFrame(salida, columns=COLUMNAS).sort_values(["fecha", "id"])
    ruta = carpeta / ARCHIVO
    temporal = ruta.with_name(ruta.name + ".tmp")
    datos.to_csv(temporal, index=False, compression="gzip", encoding="utf-8", lineterminator="\n")
    temporal.replace(ruta)
    pd.DataFrame(mapa, columns=["id", "OID"]).to_parquet(carpeta / MAPA, index=False)

    # Calidad, no privacidad: que borrar no se coma sintomas.
    exportar.ampliar_cache_regex()
    elegidos = random.Random().sample(range(len(filas)), min(MUESTRA_TERMINOS, len(filas)))
    antes = sum(len(glosario.buscar_terminos_clinicos(str(filas[i][exportar.COLUMNA]))) for i in elegidos)
    despues = sum(len(glosario.buscar_terminos_clinicos(borradas[i])) for i in elegidos)

    lote = {"creado": datetime.now().isoformat(timespec="seconds"), "filas": len(datos),
            "sha256": huella(ruta), "minimo_nivel": MINIMO_NIVEL,
            "niveles_agrupados": sorted(niveles_raros), "nombres_agrupados": sorted(nombres_raros),
            "notas_con_algo_borrado": {t: por_tipo[t] for t in TIPOS},
            "notas_vacias_tras_borrar": sum(1 for n in borradas if not n),
            "terminos_clinicos": {"notas_revisadas": len(elegidos), "antes": antes, "despues": despues}}
    (carpeta / LOTE).write_text(json.dumps(lote, indent=2, ensure_ascii=False), encoding="utf-8")
    return identidades


# ==========================================================
# AUDITAR
# ==========================================================

def correlacion_dentro_del_dia(tabla):
    """
    Spearman de la posicion de la fila contra el OID, DENTRO de cada dia.

    Los rangos se centran por dia: sin eso, dos dias de distinto tamano dan una
    correlacion falsa que no dice nada del orden.
    """
    tabla = tabla[tabla.groupby("fecha")["OID"].transform("size") > 1]
    if len(tabla) < 20:
        return None
    grupos = tabla.groupby("fecha")
    tamano = grupos["OID"].transform("size")
    centro = (tamano + 1) / 2
    rp = (grupos["posicion"].rank() - centro) / tamano
    ro = (grupos["OID"].rank() - centro) / tamano
    denominador = math.sqrt(float((rp ** 2).sum()) * float((ro ** 2).sum()))
    return float((rp * ro).sum()) / denominador if denominador else None


def _identidades_de_la_base(mapa):
    por_oid = exportar.traer_identidades(exportar._engine(), mapa["OID"].tolist())
    return {id_: por_oid.get(int(oid), em.Identidad()) for id_, oid in zip(mapa["id"], mapa["OID"])}


def auditar(carpeta=CARPETA, identidades=None, borrar_si_falla=True, informar=True):
    """
    0 si el CSV pasa. 2 si falla: el CSV se borra. 3 si no se pudo verificar la
    identidad contra la base: no se certifica, pero no se borra.
    """
    carpeta = Path(carpeta)
    ruta, ruta_mapa, ruta_lote = carpeta / ARCHIVO, carpeta / MAPA, carpeta / LOTE
    if not ruta.exists() or not ruta_mapa.exists():
        print(f"No hay tabla que auditar en {carpeta}")
        return 1
    mapa = pd.read_parquet(ruta_mapa)
    fallos = Counter()

    lote = json.loads(ruta_lote.read_text(encoding="utf-8")) if ruta_lote.exists() else {}
    if not lote:
        fallos["sin_lote"] = 1
    elif lote.get("sha256") != huella(ruta):
        fallos["archivo_modificado_despues_de_armarlo"] = 1

    sin_base = False
    if identidades is None:
        try:
            identidades = _identidades_de_la_base(mapa)
        except Exception as error:     # sin red, sin driver, sin permiso
            print(f"No se pudo leer la identidad de la base ({type(error).__name__}).")
            identidades, sin_base = {}, True

    datos = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    n = len(datos)
    if list(datos.columns) != COLUMNAS:
        fallos["columnas_distintas"] = 1

    def columna(nombre):
        return datos[nombre] if nombre in datos else pd.Series([""] * n, dtype=str)

    ids = columna("id")
    comprobaciones = {
        "id_invalido": ~ids.str.fullmatch(_ID.pattern),
        "id_repetido": ids.duplicated(),
        "fecha_no_es_un_dia": ~columna("fecha").str.fullmatch(_DIA.pattern),
        "nivel_raro": (columna("nivel").isin(lote.get("niveles_agrupados", []))
                       | columna("nivel_nombre").isin(lote.get("nombres_agrupados", []))),
        "edad_fuera_de_banda": ~columna("edad_banda").isin(bandas_de_edad()),
    }
    for nombre, malas in comprobaciones.items():
        if int(malas.sum()):
            fallos[nombre] = int(malas.sum())

    for id_, nota in zip(ids, columna("nota")):
        identidad = identidades.get(id_)
        if identidad is None and not sin_base:
            fallos["identidad_sin_verificar"] += 1
        fallos.update(revisar_nota(nota, identidad))

    en_csv, en_mapa = set(ids), set(mapa["id"])
    if en_csv - en_mapa:
        fallos["ids_que_no_estan_en_el_mapa"] = len(en_csv - en_mapa)
    if en_mapa - en_csv:
        fallos["notas_del_mapa_que_faltan"] = len(en_mapa - en_csv)

    unido = pd.DataFrame({"id": ids, "fecha": columna("fecha"), "posicion": range(n)}).merge(mapa, on="id")
    limite = 4 / math.sqrt(n) if n else 1
    azar = {"id_vs_oid": aud._spearman(unido["id"].map(lambda i: int(i, 16) if _ID.fullmatch(i) else np.nan),
                                       unido["OID"]),
            "dentro_del_dia_vs_oid": correlacion_dentro_del_dia(unido)}
    for nombre, rho in azar.items():
        if rho is not None and abs(rho) > limite:
            fallos["correlacion_" + nombre] = 1

    informe = {"filas": n, "fallos": dict(fallos), "identidad_verificada": not sin_base,
               "azar": {k: (None if v is None else round(v, 4)) for k, v in azar.items()},
               "limite_correlacion": round(limite, 4),
               **{k: lote.get(k) for k in ("sha256", "niveles_agrupados", "notas_con_algo_borrado",
                                           "notas_vacias_tras_borrar", "terminos_clinicos")}}
    informe["certificado"] = not fallos and not sin_base
    (carpeta / AUDITORIA).write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")

    if informar:
        _imprimir(informe)
    if fallos and borrar_si_falla:
        ruta.unlink(missing_ok=True)
        print(f"\nAUDITORIA FALLIDA: {ARCHIVO} BORRADO. Nada de {carpeta} debe salir de aqui.")
        return 2
    if sin_base:
        print("\nNO CERTIFICADO: falto verificar la identidad contra la base. "
              "No se borro; repite --auditar con acceso a la base.")
        return 3
    if informar:
        print(f"\nAUDITORIA SUPERADA. Lo unico que sale de {carpeta}: {ARCHIVO}.")
    return 0


def _imprimir(informe):
    n = informe["filas"] or 1
    print(f"\nAuditoria: {informe['filas']:,} filas")
    if informe["fallos"]:
        print("  FALLOS:")
        for nombre, cuenta in sorted(informe["fallos"].items()):
            print(f"    {nombre:<40}{cuenta:8,}")
    else:
        print("  fallos: 0")
    print(f"  azar (limite {informe['limite_correlacion']}): " +
          ", ".join(f"{k} {v}" for k, v in informe["azar"].items()))
    if informe.get("notas_con_algo_borrado"):
        print("  notas con algo borrado")
        for tipo, cuenta in informe["notas_con_algo_borrado"].items():
            print(f"    {tipo:<20}{cuenta:9,}{100 * cuenta / n:7.2f} %")
        print(f"  notas vacias tras borrar: {informe['notas_vacias_tras_borrar']:,}")
    if informe.get("niveles_agrupados") is not None:
        print(f"  niveles agrupados como '{OTRO}': {', '.join(informe['niveles_agrupados']) or 'ninguno'}")
    t = informe.get("terminos_clinicos")
    if t:
        print(f"  terminos clinicos en {t['notas_revisadas']:,} notas: antes {t['antes']:,}  "
              f"despues {t['despues']:,}")


# ==========================================================
# BASE CLINICA
# ==========================================================

def _desde():
    return f"FROM {exportar.TABLA} AS t LEFT JOIN {TABLA_NIVEL} AS c ON t.HCNCLAURGTR = c.OID"


def _filtro():
    from NLP.nucleo import datos
    return (f"{datos.filtro_no_vacio('t.' + exportar.COLUMNA)} "
            f"AND t.{exportar.COLUMNA_FECHA} IS NOT NULL")


def niveles_raros(engine, minimo=MINIMO_NIVEL):
    """Codigos de nivel con menos de `minimo` notas en toda la tabla. Un GROUP BY."""
    cuentas = exportar._con_reintento(engine, lambda: pd.read_sql(
        f"SELECT c.HCCODIGO AS nivel, COUNT(*) AS n {_desde()} WHERE {_filtro()} GROUP BY c.HCCODIGO",
        engine))
    cuentas["nivel"] = cuentas["nivel"].map(_texto)
    cuentas = cuentas.groupby("nivel", as_index=False)["n"].sum()
    return frozenset(cuentas.loc[(cuentas["n"] < minimo) & (cuentas["nivel"] != ""), "nivel"])


def traer(engine, muestra=None):
    """
    Las notas con dia, nivel y banda. La identidad viene solo para borrarla de
    su propia nota: vive en memoria y no se escribe.
    """
    from extraccion.__main__ import _caso_edad

    top = f"TOP {int(muestra)}" if muestra else ""
    orden = f"ORDER BY HASHBYTES('MD5', CAST(t.{exportar.LLAVE} AS varchar(20)))" if muestra else ""
    identidad = ", ".join(f"t.{c}" for c in exportar.IDENTIDAD)
    consulta = (f"SELECT {top} t.{exportar.LLAVE}, CAST(t.{exportar.COLUMNA_FECHA} AS DATE) AS fecha, "
                f"c.HCCODIGO AS nivel, c.HCDESCRIP AS nivel_nombre, {_caso_edad()} AS edad_banda, "
                f"t.{exportar.COLUMNA}, {identidad} {_desde()} WHERE {_filtro()} {orden}")
    return exportar._con_reintento(engine, lambda: pd.read_sql(consulta, engine))


def _apartar_anterior(carpeta):
    """
    El mapa nunca se pisa: si el CSV anterior ya se proceso fuera, es lo unico
    que devuelve sus filas a su triage. Se renombra con la fecha.
    """
    mapa = carpeta / MAPA
    if not mapa.exists():
        return None
    sello = datetime.fromtimestamp(mapa.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
    destino = mapa.with_name(f"mapa_local_{sello}.parquet")
    mapa.replace(destino)
    if (carpeta / LOTE).exists():
        (carpeta / LOTE).replace(carpeta / f"lote_{sello}.json")
    return destino


def exportar_tabla(muestra=None, carpeta=CARPETA, forzar=False):
    carpeta = Path(carpeta)
    if (carpeta / MAPA).exists() and not forzar:
        print(f"Ya hay una tabla armada en {carpeta}.\n"
              f"Su mapa_local.parquet es lo unico que devuelve cada fila a su triage.\n"
              f"Para rehacerla, repite con --forzar: el mapa anterior se aparta con su fecha.")
        return 1
    apartado = _apartar_anterior(carpeta) if forzar else None
    if apartado:
        print(f"Mapa anterior apartado en {apartado.name}")

    print("Conectando a la base clinica...")
    engine = exportar._engine()
    inicio = time.time()
    raros = niveles_raros(engine)
    print(f"  niveles con menos de {MINIMO_NIVEL} notas (salen como '{OTRO}'): "
          f"{', '.join(sorted(raros)) or 'ninguno'}")
    nombres = exportar.cargar_nombres(engine)
    print(f"  nombres conocidos: {len(nombres.nombres):,} de pila, {len(nombres.apellidos):,} "
          f"apellidos (en memoria, no se guardan)")
    notas = traer(engine, muestra)
    print(f"  {len(notas):,} notas leidas en {time.time() - inicio:.0f} s")
    identidades = armar(notas, nombres, carpeta, raros)
    del notas
    return auditar(carpeta, identidades=identidades)


def estado(carpeta=CARPETA):
    carpeta = Path(carpeta)
    print(carpeta)
    for nombre in (ARCHIVO, MAPA, LOTE, AUDITORIA):
        ruta = carpeta / nombre
        detalle = f"{ruta.stat().st_size / 1e6:8.2f} MB" if ruta.exists() else "       -"
        print(f"  {nombre:<22}{detalle}")
    if (carpeta / AUDITORIA).exists():
        informe = json.loads((carpeta / AUDITORIA).read_text(encoding="utf-8"))
        print(f"  filas {informe['filas']:,}   certificado {informe['certificado']}   "
              f"fallos {sum(informe['fallos'].values())}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m NLP.nube.tabla",
                                     description="Tabla de notas sin nada que lleve a la persona.")
    accion = parser.add_mutually_exclusive_group(required=True)
    accion.add_argument("--exportar", action="store_true")
    accion.add_argument("--auditar", action="store_true")
    accion.add_argument("--estado", action="store_true")
    parser.add_argument("--muestra", type=int, help="N notas repartidas por toda la tabla")
    parser.add_argument("--forzar", action="store_true", help="aparta el mapa anterior y rehace")
    args = parser.parse_args(argv)
    if args.exportar:
        return exportar_tabla(args.muestra, forzar=args.forzar)
    if args.auditar:
        return auditar()
    return estado()


if __name__ == "__main__":
    sys.exit(main())
