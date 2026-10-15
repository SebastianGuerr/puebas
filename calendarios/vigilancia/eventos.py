"""
Microdatos SIVIGILA de eventos INDIVIDUALES -> series semanales de Manizales.

    python calendarios/vigilancia/eventos.py --descargar --desde 2023          (todo el catalogo)
    python calendarios/vigilancia/eventos.py --descargar --seleccionados     (2007-2025 de lo elegido)
    python calendarios/vigilancia/eventos.py --censo      (casos de Manizales por evento y ano)
    python calendarios/vigilancia/eventos.py              (integra lo seleccionado + auditoria)

Hermano de sivigila.py, que lleva los eventos COLECTIVOS 995 y 998. Aqui van
los de ficha individual (una fila por caso): 69 columnas, iguales de 2008 a
2025. El porque de cada decision esta en calendarios/docs/VIGILANCIA.md,
seccion "Eventos individuales".

Entra:  https://portalsivigila.ins.gov.co/Microdatos/Datos_{ANIO}_{EVENTO}.xlsx,
        en calendarios/vigilancia/crudo/ (ignorada por git). El catalogo de
        archivos se lee cada vez de la lista SharePoint 'Microdatos' del portal.
Sale:   calendarios/vigilancia_sivigila_eventos.csv.gz   formato largo, la misma
            estructura que vigilancia_sivigila.csv.gz (evento, anio, semana_epi,
            fecha_inicio_semana, fecha_fin_semana, ambito, variable, valor)
        calendarios/vigilancia_sivigila_eventos_censo.csv  casos de Manizales por
            evento y ano, y el estado de cada evento (integrada / marcador /
            volumen insuficiente)
        Si el contenido no cambia, no se reescriben. Si la lista 'Microdatos' no
        responde, se usa el catalogo de la ultima consulta buena
        (crudo/catalogo_microdatos.json) y se sale con 0 y un AVISO; sin catalogo
        guardado, con 1 (calendarios/docs/VIGILANCIA.md, "Actualizacion automatica").

PRIVACIDAD, EN EL MISMO PASO DE LECTURA
    Cada fila se recorta a la LISTA BLANCA antes de existir en un DataFrame:
    evento, semana, ano, fecha de notificacion (solo para reasignar semanas
    imposibles; no se guarda), los codigos de departamento y municipio de
    ocurrencia, residencia y notificacion, ajuste, hospitalizado, tipo de caso
    y condicion final. Todo lo demas (edad, sexo, fecha de nacimiento,
    ocupacion, etnia, grupos poblacionales, aseguradora, institucion...) no se
    lee. De lo descartado solo se registra el NOMBRE de la columna.

QUE CUENTA COMO CASO
    Cada fila de la ficha es un caso notificado. Se excluyen AJUSTE 6
    (descartado) y D (error de digitacion), que es el criterio de los informes
    de evento del INS. El municipio es el de OCURRENCIA (COD_DPTO_O + COD_MUN_O,
    2 + 3 digitos): es el que filtran los tableros Power BI del INS, y empalma
    con ellos. Se guarda tambien el de notificacion (COD_MUN_N, 5 digitos).
    La semana es SEMANA, la semana epidemiologica de notificacion.
"""

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

try:                                    # inspeccion TLS corporativa en esta red
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

try:
    from calendarios.vigilancia import sivigila as S
except ImportError:                     # corrido como script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sivigila as S

AQUI = Path(__file__).resolve().parent
CRUDO = S.CRUDO
SALIDA = AQUI.parent / "vigilancia_sivigila_eventos.csv.gz"
CENSO = AQUI.parent / "vigilancia_sivigila_eventos_censo.csv"
CATALOGO_CACHE = CRUDO / "catalogo_microdatos.json"
LISTA = ("https://portalsivigila.ins.gov.co/_api/web/lists/getbytitle('Microdatos')/items"
         "?$select=FileLeafRef,CodigoEvento,NombreEvento,Modified,File/Length&$expand=File&$top=5000")

MANIZALES, CALDAS = S.MANIZALES, S.CALDAS
COLECTIVOS = {995, 998}                 # los lleva sivigila.py
# Sube cuando cambia lo que se guarda en crudo/*.evento.parquet: obliga a releer.
VERSION_RESUMEN = 2


# ==========================================================
# CATALOGO Y DESCARGA
# ==========================================================

AVISO_CAIDO = "portal del INS caído; sin datos nuevos; se usa lo ya descargado"


def lista_portal():
    """Los elementos de la lista 'Microdatos'. Lanza si el portal falla o devuelve algo que no es el catalogo."""
    r = requests.get(LISTA, headers={"Accept": "application/json;odata=nometadata"}, timeout=120)
    r.raise_for_status()
    v = r.json()["value"]
    if not v or not all({"FileLeafRef", "CodigoEvento", "File"} <= set(x) for x in v):
        raise ValueError(f"la lista Microdatos llego vacia o sin las columnas esperadas ({len(v)} elementos)")
    return v


def catalogo(refrescar=True):
    """Lista de archivos del portal: (DataFrame (evento, anio, archivo, bytes, modificado), caido).

    Si la lista no responde (el 2026-10-15 daba 500 por falta de memoria del servidor del INS) y hay un
    catalogo guardado de la ultima consulta buena, se usa ese, como powerbi.py con sus claves: `caido` trae
    entonces el error. Sin catalogo guardado, el error sube y el proceso sale con codigo 1. El guardado solo
    se sustituye con una lista valida, y de forma atomica: una respuesta rota no borra el respaldo.
    """
    caido = None
    if refrescar or not CATALOGO_CACHE.exists():
        try:
            v = lista_portal()
        except Exception as e:                   # noqa: BLE001  red, 5xx, JSON roto o lista vacia
            if not CATALOGO_CACHE.exists():
                raise RuntimeError(f"la lista Microdatos del portal del INS no responde ({e!r:.200}) "
                                   f"y no hay catalogo guardado en {CATALOGO_CACHE}") from e
            caido = f"{e!r:.200}"
            guardado = time.strftime("%Y-%m-%d", time.localtime(CATALOGO_CACHE.stat().st_mtime))
            print(f"AVISO: la lista Microdatos del portal del INS no responde ({caido}); "
                  f"se usa el catalogo guardado el {guardado}", flush=True)
        else:
            CRUDO.mkdir(parents=True, exist_ok=True)
            tmp = CATALOGO_CACHE.with_name(CATALOGO_CACHE.name + ".tmp")
            tmp.write_text(json.dumps(v), encoding="utf-8")
            tmp.replace(CATALOGO_CACHE)
    v = json.loads(CATALOGO_CACHE.read_text(encoding="utf-8"))
    return pd.DataFrame({
        "evento": [int(x["CodigoEvento"]) for x in v],
        "anio": [int(x["FileLeafRef"].split("_")[1]) for x in v],
        "archivo": [x["FileLeafRef"] for x in v],
        "bytes": [int(x["File"]["Length"]) for x in v],
        "modificado": [x["Modified"] for x in v],
    }).sort_values(["evento", "anio"]).reset_index(drop=True), caido


def descargar_plan(plan, tolerar=False):
    """Baja, de uno en uno, los archivos del plan (evento, anio). Reanudable: ver S.descargar.

    Devuelve (bajados, fallidos). Con tolerar=True (catalogo de respaldo: el portal ya fallo) un archivo que
    no baja se anota y se sigue; sin el, la excepcion sube como siempre."""
    total = plan["bytes"].sum()
    hecho = 0
    bajados, fallidos = [], []
    for fila in plan.itertuples():
        destino = CRUDO / fila.archivo
        if not (destino.exists() and destino.stat().st_size == fila.bytes):
            t = time.time()
            try:
                if S.descargar(fila.evento, fila.anio) is not None:
                    bajados.append(fila.archivo)
            except Exception as e:               # noqa: BLE001
                if not tolerar:
                    raise
                fallidos.append(fila.archivo)
                print(f"    {fila.archivo}: no se pudo bajar con el portal caido ({e!r:.150})", flush=True)
            print(f"    ({time.time() - t:.0f} s)", flush=True)
        hecho += fila.bytes
        print(f"[{hecho / 1e6:.0f}/{total / 1e6:.0f} MB] {fila.archivo}", flush=True)
    return bajados, fallidos


# ==========================================================
# LECTURA (lista blanca en el mismo paso)
# ==========================================================

# Nombres tras S.normalizar (minusculas; 'ANO' -> 'anio').
BLANCA = ["cod_eve", "semana", "anio", "fec_not", "ini_sin", "fec_con",
          "cod_dpto_o", "cod_mun_o", "cod_dpto_r", "cod_mun_r", "cod_dpto_n", "cod_mun_n",
          "ajuste", "pac_hos", "tip_cas", "con_fin"]
OBLIGATORIAS = ("cod_eve", "semana", "cod_mun_o", "cod_dpto_o")


def limpio(serie):
    """Quita la forma de formula (="01"), espacios y el .0 de los numeros leidos como float."""
    return (serie.astype(str).str.strip().str.replace(r'^="?|"$', "", regex=True).str.strip()
            .str.replace(r"\.0$", "", regex=True))


def leer_individual(ruta):
    """Excel de ficha individual -> (tabla con SOLO la lista blanca, descartadas, nombre del evento)."""
    from python_calamine import CalamineWorkbook

    libro = CalamineWorkbook.from_path(str(ruta))
    nombre, fila_cab = S.buscar_cabecera(libro, OBLIGATORIAS)
    hoja = libro.get_sheet_by_name(nombre)
    filas = hoja.iter_rows()
    for _ in range(fila_cab):
        next(filas)
    cabecera = [S.normalizar(c) for c in next(filas)]
    idx = [i for i, c in enumerate(cabecera) if c in BLANCA and c not in cabecera[:i]]
    # El nombre del evento es texto del catalogo del INS, no de la persona.
    i_nom = cabecera.index("nombre_evento") if "nombre_evento" in cabecera else None
    nombres = [cabecera[i] for i in idx]
    descartadas = [c for c in cabecera if c not in BLANCA]
    datos, evento_nombre = [], {}
    for f in filas:
        datos.append([f[i] if i < len(f) else None for i in idx])
        if i_nom is not None and i_nom < len(f):
            evento_nombre[f[i_nom]] = evento_nombre.get(f[i_nom], 0) + 1
    del filas, hoja, libro
    tabla = pd.DataFrame(datos, columns=nombres)
    del datos
    gc.collect()
    nom = max(evento_nombre, key=evento_nombre.get) if evento_nombre else ""
    nom = str(nom).strip().removeprefix('="').removesuffix('"').strip()
    return tabla, descartadas, nom, len(cabecera)


def municipio(dpto, mun):
    """Codigo DANE de 5 digitos desde departamento (2) y municipio (3 o 5)."""
    d, m = limpio(dpto), limpio(mun)
    cinco = m.str.len() == 5
    return pd.Series(np.where(cinco, m, d.str.zfill(2) + m.str.zfill(3)), index=m.index)


def fecha(serie):
    """Fechas de la ficha individual -> Timestamp. Llegan como fecha de Excel o como
    texto, con forma de formula y a veces con hora ('5/03/2025 10:12:00 a. m.').
    El texto es dia/mes/ano: medido en 2025, d/m valida el 100 % de las filas y
    m/d menos de la mitad. S.fecha no sirve aqui: corta a 10 caracteres y pierde
    los dias de un digito."""
    no_texto = serie.map(lambda x: not isinstance(x, str))
    f = pd.to_datetime(serie.where(no_texto), errors="coerce")
    t = limpio(serie.where(~no_texto)).str.split(" ").str[0]
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        f = f.fillna(pd.to_datetime(t, format=formato, errors="coerce"))
    return f


def semana_epi(fechas):
    """Serie de fechas -> (ano epidemiologico, semana), con la regla de S.semana_de_fecha."""
    unicas = {d: S.semana_de_fecha(d) for d in fechas.dropna().unique()}
    par = fechas.map(lambda d: unicas.get(d) if pd.notna(d) else None)
    return (par.map(lambda x: x[0] if x else np.nan), par.map(lambda x: x[1] if x else np.nan))


def limpiar_individual(tabla, anio):
    notas = {"filas_leidas": len(tabla)}
    for c in ("semana", "anio", "cod_eve", "pac_hos", "tip_cas", "con_fin"):
        if c in tabla.columns:
            tabla[c] = pd.to_numeric(limpio(tabla[c]), errors="coerce")
    tabla["ajuste"] = limpio(tabla["ajuste"]).str.upper() if "ajuste" in tabla.columns else ""
    # Las fechas exactas se leen solo para convertirlas en semana y se tiran en
    # este mismo paso: ninguna llega al resumen.
    for c in ("fec_not", "ini_sin", "fec_con"):
        tabla[c] = fecha(tabla[c]) if c in tabla.columns else pd.NaT
    tabla["mun_o"] = municipio(tabla["cod_dpto_o"], tabla["cod_mun_o"])
    tabla["mun_r"] = municipio(tabla["cod_dpto_r"], tabla["cod_mun_r"]) if "cod_mun_r" in tabla else ""
    tabla["mun_n"] = municipio(tabla["cod_dpto_n"], tabla["cod_mun_n"]) if "cod_mun_n" in tabla else ""
    notas["codigos_evento"] = ",".join(f"{int(k)}:{v}" for k, v in tabla["cod_eve"].value_counts().items()
                                       if pd.notna(k))
    notas["ajustes"] = ",".join(f"{k}:{v}" for k, v in tabla["ajuste"].value_counts().items())
    anulada = tabla["ajuste"].isin(["6", "D"])
    notas["filas_ajuste_6_o_D"] = int(anulada.sum())
    notas["manizales_ajuste_6_o_D"] = int((anulada & (tabla["mun_o"] == MANIZALES)).sum())
    tabla = tabla[~anulada]
    tabla = S.corregir_semanas(tabla, anio, notas)
    # Que fecha sigue la columna SEMANA en este archivo. No es la semana de
    # notificacion: el INS la define por evento (inicio de sintomas, consulta o
    # notificacion) y en algunos eventos cambia de un ano a otro.
    for c in ("fec_not", "ini_sin", "fec_con"):
        a, w = semana_epi(tabla[c])
        notas[f"semana_igual_{c}_pct"] = round(100 * ((a == anio) & (w == tabla["semana"])).mean(), 1)
    # La semana de CONSULTA, con una definicion que no cambia entre anos.
    tabla["anio_consulta"], tabla["semana_consulta"] = semana_epi(tabla["fec_con"])
    notas["fec_con_sin_fecha"] = int(tabla["fec_con"].isna().sum())
    notas["consulta_en_otro_anio"] = int((tabla["anio_consulta"] != anio).sum())
    tabla = tabla.drop(columns=["fec_not", "ini_sin", "fec_con"])
    return tabla, notas


def resumir_individual(tabla):
    """Tabla limpia -> conteos por semana. Nada de fila a fila sale de aqui."""
    t = tabla.assign(
        o_mzl=tabla["mun_o"] == MANIZALES, n_mzl=tabla["mun_n"] == MANIZALES,
        r_mzl=tabla["mun_r"] == MANIZALES, o_cal=tabla["mun_o"].str[:2] == CALDAS,
        hos=tabla["pac_hos"] == 1)
    g = t.groupby(["cod_eve", "semana"])
    r = pd.DataFrame({
        "casos_colombia": g.size(),
        "casos_caldas": g["o_cal"].sum(),
        "casos_ocurrencia": g["o_mzl"].sum(),
        "casos_residencia": g["r_mzl"].sum(),
        "casos_notificacion": g["n_mzl"].sum(),
        "casos_ocurrencia_hospitalizados": g.apply(lambda s: (s["o_mzl"] & s["hos"]).sum(),
                                                   include_groups=False),
    }).reset_index()
    r = r.astype({c: int for c in r.columns})
    # Manizales (ocurrencia) por semana de CONSULTA; el ano puede ser otro.
    m = t[t["o_mzl"] & t["semana_consulta"].notna()]
    rc = (m.groupby(["cod_eve", "anio_consulta", "semana_consulta"]).size()
           .rename("casos_ocurrencia_semana_consulta").reset_index().astype(int))
    return r, rc


# ----------------------------------------------------------
# 349: ETA colectivo. Una fila por BROTE, 137 columnas, otra ficha.
# ----------------------------------------------------------
# cod_mun es el municipio de procedencia del brote y pierde el cero inicial
# (4 o 5 digitos); Caldas es 17, asi que Manizales siempre es 17001.
# Hasta 2017 la ficha era otra (la del antiguo 350, 188-230 columnas): el
# municipio viene en cod_mun_ (5 digitos, el que notifica; el de procedencia,
# cod_mun_pr, trae solo 3 digitos y no tiene departamento al lado) y los
# enfermos en 'enfermos'. Se renombran a los de la ficha nueva. En 2015-2017
# Manizales da 0 brotes por cualquiera de los dos criterios (medido).
ANTIGUA_349 = {"cod_mun_": "cod_mun", "enfermos": "total_enf"}
BLANCA_349 = ["semana", "anio", "cod_eve", "fec_not", "cod_mun", "total_enf", "ajuste"] + list(ANTIGUA_349)


def leer_349(ruta):
    from python_calamine import CalamineWorkbook

    libro = CalamineWorkbook.from_path(str(ruta))
    try:
        nombre, fila_cab = S.buscar_cabecera(libro, ("semana", "cod_mun", "total_enf"))
    except ValueError:
        nombre, fila_cab = S.buscar_cabecera(libro, ("semana", "cod_mun_", "enfermos"))
    hoja = libro.get_sheet_by_name(nombre)
    filas = hoja.iter_rows()
    for _ in range(fila_cab):
        next(filas)
    cabecera = [S.normalizar(c) for c in next(filas)]
    if "cod_mun" not in cabecera:
        cabecera = [ANTIGUA_349.get(c, c) for c in cabecera]
    idx = [i for i, c in enumerate(cabecera) if c in BLANCA_349 and c not in cabecera[:i]]
    datos = [[f[i] if i < len(f) else None for i in idx] for f in filas]
    del filas, hoja, libro
    tabla = pd.DataFrame(datos, columns=[cabecera[i] for i in idx])
    return tabla, [c for c in cabecera if c not in BLANCA_349], "ETA COLECTIVO", len(cabecera)


def limpiar_resumir_349(tabla, anio):
    notas = {"filas_leidas": len(tabla), "formato": "brote_137_columnas"}
    for c in ("semana", "anio", "cod_eve", "total_enf"):
        tabla[c] = pd.to_numeric(limpio(tabla[c]), errors="coerce")
    tabla["ajuste"] = limpio(tabla["ajuste"]).str.upper() if "ajuste" in tabla else ""
    tabla["fec_not"] = S.fecha(tabla["fec_not"])
    tabla["mun_o"] = limpio(tabla["cod_mun"]).str.zfill(5)
    anulada = tabla["ajuste"].isin(["6", "D"])
    notas["filas_ajuste_6_o_D"] = int(anulada.sum())
    tabla = S.corregir_semanas(tabla[~anulada], anio, notas)
    t = tabla.assign(mzl=tabla["mun_o"] == MANIZALES, cal=tabla["mun_o"].str[:2] == CALDAS)
    t["enf_mzl"] = t["total_enf"].where(t["mzl"], 0)
    g = t.groupby(["cod_eve", "semana"])
    r = pd.DataFrame({"casos_colombia": g.size(), "casos_caldas": g["cal"].sum(),
                      "casos_ocurrencia": g["mzl"].sum(),
                      "enfermos_ocurrencia": g["enf_mzl"].sum()}).reset_index()
    return r.astype({c: int for c in r.columns}), notas


def procesar_archivo(evento, anio, ruta):
    """Un archivo -> resumen en disco al lado del crudo. Si ya esta hecho con este crudo, no relee."""
    resumen = ruta.with_suffix(".evento.parquet")
    consulta = ruta.with_suffix(".consulta.parquet")
    notas_ruta = ruta.with_suffix(".evento.json")
    marca = f"{ruta.stat().st_size}-{VERSION_RESUMEN}"
    if resumen.exists() and notas_ruta.exists():
        notas = json.loads(notas_ruta.read_text(encoding="utf-8"))
        if str(notas.get("marca")) == marca:
            rc = pd.read_parquet(consulta) if consulta.exists() else None
            return pd.read_parquet(resumen), notas, rc
    t = time.time()
    rc = None
    if evento == 349:
        tabla, descartadas, nombre, ncol = leer_349(ruta)
        r, notas = limpiar_resumir_349(tabla, anio)
    else:
        tabla, descartadas, nombre, ncol = leer_individual(ruta)
        tabla, notas = limpiar_individual(tabla, anio)
        r, rc = resumir_individual(tabla)
    del tabla
    gc.collect()
    r.insert(0, "anio", anio)
    notas.update(marca=marca, nombre_evento=nombre, descartadas=",".join(descartadas),
                 n_columnas=ncol, segundos=round(time.time() - t, 1))
    r.to_parquet(resumen)
    if rc is not None:
        rc.to_parquet(consulta)
    notas_ruta.write_text(json.dumps(notas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {ruta.name}: {notas['filas_leidas']} filas, {ncol} columnas, {notas['segundos']} s",
          flush=True)
    return r, notas, rc


def procesar_todo(cat):
    """Todo lo del catalogo que ya esta en crudo/ -> {(evento, anio): (resumen, notas)}."""
    hechos = {}
    for fila in cat.itertuples():
        ruta = CRUDO / fila.archivo
        if not (ruta.exists() and ruta.stat().st_size == fila.bytes):
            continue
        try:
            hechos[(fila.evento, fila.anio)] = procesar_archivo(fila.evento, fila.anio, ruta)
        except ValueError as e:                  # ficha que no es la individual: se dice y se sigue
            print(f"  {ruta.name} NO PROCESADO: {e}")
            hechos[(fila.evento, fila.anio)] = (None, {"error": str(e)[:300]}, None)
    return hechos


# ==========================================================
# CENSO Y SELECCION
# ==========================================================

RECIENTES = (2023, 2024, 2025)
# Media de casos de Manizales (ocurrencia) por semana en RECIENTES para entrar
# como serie. Fijado por el propietario el 2026-09-28: "al menos ~1 por semana".
UMBRAL = 1.0
MARCADORES = {452: "polvora", 349: "brotes de ETA", 348: "IRAG inusitado"}
# En 2026 el INS notifica con codigos agrupados que no existen en los
# microdatos. Se construyen sumando los antiguos, para empalmar con Power BI.
AGRUPADOS = {
    365: ("INTOXICACIONES (suma de 360-414)", [360, 370, 380, 390, 400, 410, 412, 414]),
    813: ("TUBERCULOSIS (suma de 810, 820 y 825)", [810, 820, 825]),
}


def censo(cat, hechos):
    # cat: el catalogo COMPLETO (todos los anos), para saber que se publica.
    """Una fila por evento: nombre, casos de Manizales por ano, media semanal reciente, estado."""
    filas = []
    for evento, g in cat.groupby("evento"):
        fila = {"evento": evento, "nombre": "", "anios_en_portal": f"{g['anio'].min()}-{g['anio'].max()}"}
        casos = {}
        for anio in sorted(g["anio"]):
            r, n, _ = hechos.get((evento, anio), (None, {}, None))
            if n.get("nombre_evento"):
                fila["nombre"] = n["nombre_evento"]
            if r is not None:
                casos[anio] = int(r["casos_ocurrencia"].sum())
            elif "error" in n:
                fila["error"] = n["error"]
        for anio in range(2015, 2026):
            fila[f"casos_{anio}"] = casos.get(anio, np.nan)
        # Anos recientes: 2023-2025, o los tres ultimos publicados si el evento
        # dejo de salir antes (entonces no puede entrar: no hay continuidad).
        base = [a for a in RECIENTES if a in casos] or sorted(casos)[-3:]
        semanas = sum(S.semanas_del_anio(a) for a in base)
        fila["anios_base"] = f"{base[0]}-{base[-1]}" if base else ""
        fila["media_semanal_base"] = round(sum(casos[a] for a in base) / semanas, 3) if base else np.nan
        publicado = g["anio"].max() >= RECIENTES[0]
        if evento in MARCADORES:
            estado = "marcador"
        elif not base:
            estado = "sin procesar"
        elif not publicado:
            estado = f"sin publicar desde {g['anio'].max()}"
        elif fila["media_semanal_base"] >= UMBRAL:
            estado = "integrada"
        else:
            estado = "volumen insuficiente"
        fila["estado"] = estado
        filas.append(fila)
    c = pd.DataFrame(filas)
    # Los agregados de 2026 (365, 813): suma de sus codigos, solo en los anos
    # en que estan todos los que el portal publica ese ano.
    aggs = []
    for cod, (nombre, partes) in AGRUPADOS.items():
        sub = c[c["evento"].isin(partes)]
        agg = {"evento": cod, "nombre": nombre, "anios_en_portal": "suma", "anios_base": "2023-2025"}
        for anio in range(2015, 2026):
            publicados = set(cat.loc[(cat["anio"] == anio) & cat["evento"].isin(partes), "evento"])
            v = sub.loc[sub["evento"].isin(publicados), f"casos_{anio}"]
            agg[f"casos_{anio}"] = v.sum() if len(v) and v.notna().all() else np.nan
        agg["media_semanal_base"] = round(sum(agg[f"casos_{a}"] for a in RECIENTES)
                                          / sum(S.semanas_del_anio(a) for a in RECIENTES), 3)
        agg["estado"] = "integrada" if agg["media_semanal_base"] >= UMBRAL else "volumen insuficiente"
        aggs.append(agg)
    c = pd.concat([c, pd.DataFrame(aggs)], ignore_index=True)
    return c.sort_values(["estado", "media_semanal_base"], ascending=[True, False])


def seleccionados(c):
    """Eventos cuya serie se construye: integrados, marcadores y los componentes de los agregados."""
    e = set(c.loc[c["estado"].isin(["integrada", "marcador"]), "evento"])
    for cod, (_, partes) in AGRUPADOS.items():
        if cod in e:
            e |= set(partes)
    return sorted(e - set(AGRUPADOS))


# ==========================================================
# SERIES
# ==========================================================

VARIABLES = {  # columna del resumen -> (ambito, variable)
    "casos_ocurrencia": ("manizales", "casos_ocurrencia"),
    "casos_notificacion": ("manizales", "casos_notificacion"),
    "casos_residencia": ("manizales", "casos_residencia"),
    "casos_ocurrencia_hospitalizados": ("manizales", "casos_ocurrencia_hospitalizados"),
    "casos_ocurrencia_semana_consulta": ("manizales", "casos_ocurrencia_semana_consulta"),
    "casos_caldas": ("caldas", "casos_ocurrencia"),
    "casos_colombia": ("colombia", "casos_total"),
}
VARIABLES_349 = {
    "casos_ocurrencia": ("manizales", "brotes"),
    "enfermos_ocurrencia": ("manizales", "enfermos"),
    "casos_caldas": ("caldas", "brotes"),
    "casos_colombia": ("colombia", "brotes"),
}


def rejilla(evento, anio, r):
    """Resumen de un archivo -> una fila por semana del ano, con CERO donde no hubo casos.

    Un GROUP BY no emite ceros: sin esta rejilla, una semana sin casos seria un
    hueco y no un cero (la trampa del triage 0-4, docs/CONTEXTO.md 2026-09-28).
    """
    semanas = pd.RangeIndex(1, S.semanas_del_anio(anio) + 1, name="semana")
    cols = [c for c in r.columns if c.startswith(("casos_", "enfermos_"))]
    w = r.groupby("semana")[cols].sum().reindex(semanas, fill_value=0)
    w.insert(0, "anio", anio)
    w.insert(0, "evento", evento)
    return w.reset_index()


def consulta_por_semana(c, hechos, cat, ancho):
    """Manizales por semana epidemiologica de la fecha de CONSULTA (fec_con).

    Suma sobre TODOS los archivos del evento, porque un caso notificado en el
    archivo de 2025 puede haber consultado en 2024. Se pone en la rejilla de
    los anos que ya tiene el evento, con cero donde no hubo consultas.
    """
    filas = []
    for (e, a), (_, _, rc) in hechos.items():
        if rc is not None and len(rc):
            filas.append(rc.assign(evento=e))
    if not filas:
        return pd.DataFrame(columns=["evento", "anio", "semana", "casos_ocurrencia_semana_consulta"])
    rc = pd.concat(filas, ignore_index=True)
    rc = (rc.groupby(["evento", "anio_consulta", "semana_consulta"])["casos_ocurrencia_semana_consulta"]
            .sum().reset_index().rename(columns={"anio_consulta": "anio", "semana_consulta": "semana"}))
    rejilla_ = ancho[["evento", "anio", "semana"]].drop_duplicates()
    out = rejilla_.merge(rc, how="left", on=["evento", "anio", "semana"])
    out["casos_ocurrencia_semana_consulta"] = out["casos_ocurrencia_semana_consulta"].fillna(0)
    # Los eventos sin fecha de consulta (349) quedan fuera.
    con = {e for (e, _), (_, _, x) in hechos.items() if x is not None}
    return out[out["evento"].isin(con)]


def series(c, hechos, cat):
    partes = []
    for evento in seleccionados(c):
        for (e, anio), (r, _, _) in sorted(hechos.items()):
            if e == evento and r is not None:
                partes.append(rejilla(evento, anio, r))
    ancho = pd.concat(partes, ignore_index=True)
    ancho = ancho.merge(consulta_por_semana(c, hechos, cat, ancho), how="left",
                        on=["evento", "anio", "semana"])
    # Agregados de 2026: suma de sus codigos, solo en los anos completos.
    for cod, (_, partes) in AGRUPADOS.items():
        if cod not in set(c.loc[c["estado"] == "integrada", "evento"]):
            continue
        sub = ancho[ancho["evento"].isin(partes)]
        completos = [a for a in sub["anio"].unique()
                     if set(sub.loc[sub["anio"] == a, "evento"])
                     == set(cat.loc[(cat["anio"] == a) & cat["evento"].isin(partes), "evento"])]
        suma = sub[sub["anio"].isin(completos)].groupby(["anio", "semana"]).sum(numeric_only=True)
        suma = suma.drop(columns="evento").reset_index()
        suma.insert(0, "evento", cod)
        ancho = pd.concat([ancho, suma], ignore_index=True)

    largo = []
    for evento, g in ancho.groupby("evento"):
        mapa = VARIABLES_349 if evento == 349 else VARIABLES
        for col, (ambito, var) in mapa.items():
            if col not in g.columns or g[col].isna().all():
                continue
            l = g[["evento", "anio", "semana", col]].rename(columns={col: "valor"})
            l["ambito"], l["variable"] = ambito, var
            largo.append(l)
        if evento in MARCADORES:
            col = "casos_ocurrencia"
            l = g[["evento", "anio", "semana"]].assign(valor=(g[col] > 0).astype(int),
                                                       ambito="manizales", variable="semana_con_casos")
            largo.append(l)
    largo = pd.concat(largo, ignore_index=True).dropna(subset=["valor"])
    largo["valor"] = largo["valor"].astype(int)
    f = {(a, s): S.fechas_semana(a, s) for a, s in largo[["anio", "semana"]].drop_duplicates().itertuples(index=False)}
    largo["fecha_inicio_semana"] = [f[(a, s)][0] for a, s in zip(largo["anio"], largo["semana"])]
    largo["fecha_fin_semana"] = [f[(a, s)][1] for a, s in zip(largo["anio"], largo["semana"])]
    largo = largo.rename(columns={"semana": "semana_epi"})
    largo = largo[["evento", "anio", "semana_epi", "fecha_inicio_semana", "fecha_fin_semana",
                   "ambito", "variable", "valor"]]
    return largo.sort_values(["evento", "ambito", "variable", "anio", "semana_epi"])


# ==========================================================
# AUDITORIA
# ==========================================================

def auditar(largo, c, hechos):
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    print("\n=== Censo: casos de Manizales (ocurrencia) por ano ===")
    cols = ["evento", "nombre"] + [f"casos_{a}" for a in range(2015, 2026)] + ["media_semanal_base", "estado"]
    t = c[cols].copy()
    t["nombre"] = t["nombre"].str[:34]
    print(t.to_string(index=False, na_rep="."))

    print("\n=== Calidad por archivo de los eventos con serie ===")
    filas = []
    for (e, a), (r, n, _) in sorted(hechos.items()):
        if e not in seleccionados(c) or r is None:
            continue
        filas.append({"evento": e, "anio": a, "columnas": n.get("n_columnas"),
                      "filas_pais": n.get("filas_leidas"),
                      "codigos": n.get("codigos_evento", ""),
                      "ajuste_6_D_pais": n.get("filas_ajuste_6_o_D"),
                      "ajuste_6_D_mzl": n.get("manizales_ajuste_6_o_D"),
                      "anio_distinto": n.get("anio_distinto"),
                      "semana_fuera": n.get("semana_fuera_de_rango"),
                      "semana_reasignada": n.get("semana_reasignada_por_fec_not", 0),
                      # % de filas cuya SEMANA es la de esa fecha: dice que sigue SEMANA
                      "sem=not%": n.get("semana_igual_fec_not_pct"),
                      "sem=ini%": n.get("semana_igual_ini_sin_pct"),
                      "sem=con%": n.get("semana_igual_fec_con_pct"),
                      "sin_fec_con": n.get("fec_con_sin_fecha")})
    print(pd.DataFrame(filas).to_string(index=False))

    print("\n=== Por evento y ano: Manizales ===")
    m = largo[largo["ambito"] == "manizales"]
    for evento, g in m.groupby("evento"):
        base = "brotes" if evento == 349 else "casos_ocurrencia"
        p = g.pivot_table(index="anio", columns="variable", values="valor", aggfunc="sum")
        o = g[g["variable"] == base]
        p["semanas"] = o.groupby("anio").size()
        p["semanas_con_casos"] = o.assign(x=o["valor"] > 0).groupby("anio")["x"].sum()
        p["max_semanal"] = o.groupby("anio")["valor"].max()
        p["cambio_vs_anio_previo"] = (p[base] / p[base].shift()).round(2)
        print(f"-- {evento}")
        print(p.to_string())


# ==========================================================
# PRINCIPAL
# ==========================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--eventos", nargs="+", type=int, help="por defecto, todo el catalogo individual")
    ap.add_argument("--desde", type=int, default=2007)
    ap.add_argument("--hasta", type=int, default=time.localtime().tm_year)   # lo no publicado no esta en el catalogo
    ap.add_argument("--forzar", action="store_true", help="escribe aunque cambien o falten filas del pasado")
    ap.add_argument("--descargar", action="store_true", help="solo descarga, de menor a mayor")
    ap.add_argument("--seleccionados", action="store_true",
                    help="con --descargar: solo los eventos que el censo integra o marca")
    ap.add_argument("--ultimos", type=int, metavar="N",
                    help="con --descargar: solo los N ultimos anos publicados de cada evento")
    ap.add_argument("--sin-red", action="store_true", help="usa el catalogo guardado en crudo/")
    args = ap.parse_args()

    cat, caido = catalogo(refrescar=not args.sin_red)
    cat = cat[~cat["evento"].isin(COLECTIVOS) & cat["anio"].between(args.desde, args.hasta)]
    if args.eventos:
        cat = cat[cat["evento"].isin(args.eventos)]
    if args.descargar:
        plan = cat
        if args.seleccionados:
            plan = plan[plan["evento"].isin(seleccionados(pd.read_csv(CENSO)))]
        if args.ultimos:
            plan = plan[plan.groupby("evento")["anio"].rank(ascending=False) <= args.ultimos]
        bajados, fallidos = descargar_plan(plan.sort_values("bytes"), tolerar=caido is not None)
        if caido is not None:
            # Los microdatos anuales llegan ~8 meses tarde: un dia sin portal no es un fallo de frescura.
            aviso = (AVISO_CAIDO if not bajados else
                     f"portal del INS caido; con el catalogo guardado se bajaron {len(bajados)} archivos")
            if fallidos:
                aviso += f" ({len(fallidos)} no bajaron: {', '.join(fallidos[:5])})"
            print(f"AVISO: {aviso}", flush=True)
        return

    hechos = procesar_todo(cat)
    c = censo(cat, hechos)
    largo = series(c, hechos, cat)
    sys.path.insert(0, str(AQUI.parents[1]))
    from calendarios.actualizacion import cambios_largo, escribir_si_cambia
    previo = pd.read_csv(SALIDA) if SALIDA.exists() else None
    perdidas, cambiadas = cambios_largo(previo, largo, ["evento", "anio", "semana_epi", "ambito", "variable"])
    print(f"{SALIDA.name}: frente al archivo previo, {perdidas} filas desaparecerian y {cambiadas} valores cambiarian")
    if (perdidas or cambiadas) and not args.forzar:
        sys.exit(f"{SALIDA.name}: no se escribe para no mover el pasado (--forzar para aceptarlo)")
    # Sin cambios, no se tocan: un .gz reescrito cambia de bytes (la cabecera lleva la hora) y git lo ve.
    escritos = [r.name for t, r in ((c, CENSO), (largo, SALIDA)) if escribir_si_cambia(t, r, index=False)]
    print(f"\n{SALIDA.name}: {len(largo)} filas; eventos {sorted(largo['evento'].unique())}")
    print(f"{CENSO.name}: {len(c)} eventos")
    auditar(largo, c, hechos)
    final = f"escritos: {', '.join(escritos)}" if escritos else "sin cambios, no se toca ningun archivo"
    print(f"\n{final}" + (f" | AVISO: {AVISO_CAIDO}" if caido is not None else ""), flush=True)


if __name__ == "__main__":
    main()
