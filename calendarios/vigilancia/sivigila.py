"""
Microdatos SIVIGILA del INS -> series semanales de vigilancia para Manizales.

    python calendarios/vigilancia/sivigila.py                    (995 y 998, 2011-2025)
    python calendarios/vigilancia/sivigila.py --sin-descargar    (solo lo que ya esta en crudo/)
    python -m calendarios.vigilancia.sivigila --solo-descargar --eventos 998
    python calendarios/vigilancia/sivigila.py --cabeceras        (solo nombres de columna)

Entra:  https://portalsivigila.ins.gov.co/Microdatos/Datos_{ANIO}_{EVENTO}.xlsx,
        bajados a calendarios/vigilancia/crudo/ (ignorada por git: los archivos
        traen nombre, cargo, telefono, correo y documento de quien notifica).
Sale:   calendarios/vigilancia_sivigila.csv.gz               formato largo
        calendarios/vigilancia_sivigila_instituciones.csv.gz  Manizales, por UPGD (995)
        y, al final, la auditoria impresa (ver calendarios/docs/VIGILANCIA.md).
        Si una corrida no procesa un evento, sus filas se conservan del archivo previo.

QUE EVENTOS
    995 (morbilidad por IRA, colectiva semanal): cada institucion (UPGD) notifica
    cada semana las consultas por IRA (J00-J22) Y las consultas por todas las
    causas, en 7 grupos de edad. Tiene denominador. 2011 es otra ficha y no se
    procesa; 2012 no trae las columnas tot_* y se reconstruyen.
    998 (morbilidad por EDA, colectiva): solo casos, en 18 edades (2011, 2012 y
    2014: tabla municipal sin edad). Sin denominador propio: la proporcion se
    calcula contra las consultas por todas las causas del 995 del mismo ambito
    y semana.

PRIVACIDAD, EN EL MISMO PASO DE LECTURA
    Cada fila del Excel se recorta a la LISTA BLANCA de columnas antes de
    guardarse en memoria. Lo que no esta en la lista no llega a existir en un
    DataFrame, y de las columnas que se descartan solo se registra el NOMBRE.
    El nombre y el codigo de la institucion (UPGD) no son dato personal y se
    conservan.

MEMORIA
    Un archivo a la vez, secuencial. Cada archivo se reduce a un resumen por
    UPGD x semana para Caldas y por semana para el pais, que se guarda al lado
    del crudo (crudo/*.resumen.parquet). La siguiente corrida lee el resumen y
    no vuelve a abrir el Excel mientras el crudo no cambie de tamano.

SEMANA EPIDEMIOLOGICA -> FECHAS
    Domingo a sabado. La semana 1 es la que contiene el 4 de enero (la de la
    regla MMWR: la primera semana con al menos cuatro dias del ano nuevo).
    Comprobado contra el calendario del INS y contra fec_not; ver VIGILANCIA.md.
"""

import argparse
import gc
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

AQUI = Path(__file__).resolve().parent
CRUDO = AQUI / "crudo"
RAIZ = AQUI.parent.parent
SALIDA = AQUI.parent / "vigilancia_sivigila.csv.gz"
SALIDA_INSTITUCIONES = AQUI.parent / "vigilancia_sivigila_instituciones.csv.gz"
TRIAGE_EDAD = RAIZ / "salidas" / "triage_edad.parquet"

URL = "https://portalsivigila.ins.gov.co/Microdatos/Datos_{anio}_{evento}.xlsx"
REINTENTOS, ESPERA, TIMEOUT = 5, 5.0, 120
BLOQUE = 1 << 20
# Sube cuando cambia lo que se guarda en crudo/*.resumen.parquet: obliga a releer.
VERSION_RESUMEN = {995: 4, 998: 5}

MANIZALES = "17001"
CALDAS = "17"

# Los 7 grupos de la ficha 995 (FOR-R02.0000-044 V:03, 2015):
# < 1, 1, 2 a 4, 5 a 19, 20 a 39, 40 a 59, >= 60.
GRUPOS = ["menor_1", "1", "2_4", "5_19", "20_39", "40_59", "60_mas"]

# Bloques de la ficha: prefijo de las 7 columnas por edad -> (columna total, nombre).
BLOQUES_995 = {
    "iracext":  ("tot_iraext", "consultas_ira"),
    "totcext":  ("tot_exturg", "consultas_todas_causas"),
    "grupoh":   ("tot_irag",   "hospitalizaciones_irag"),
    "hospital": ("tot_cau_h",  "hospitalizaciones_todas_causas"),
    "irauci":   ("tot_irauci", "uci_irag"),
    "totuci":   ("tot_h_uci",  "uci_todas_causas"),
    "mteira":   ("tot_mu_ira", "muertes_irag"),
    "mtetot":   ("tot_muerte", "muertes_todas_causas"),
}
# Numerador / denominador de cada proporcion.
PARES = [
    ("consultas_ira", "consultas_todas_causas", "proporcion_consultas_ira"),
    ("hospitalizaciones_irag", "hospitalizaciones_todas_causas", "proporcion_hospitalizaciones_irag"),
    ("uci_irag", "uci_todas_causas", "proporcion_uci_irag"),
]

# Identificacion de la fila. Todo lo demas que no sea un conteo de BLOQUES_995
# se descarta al leer. En 2025 lo descartado es: diligencia (nombre), cargo,
# telefono, correo, num_con (un numero de documento), fec_aju, nit_upgd, nom_eve.
IDENTIFICACION = ["semana", "anio", "fec_not", "cod_pre", "cod_sub", "cod_mun",
                  "ajuste", "nom_upgd", "ndep_notif", "nmun_notif", "cod_eve"]


# ==========================================================
# SEMANA EPIDEMIOLOGICA
# ==========================================================

def inicio_semana_1(anio):
    """Domingo que abre la SE1: el de la semana (dom-sab) que contiene el 4 de enero."""
    cuatro = date(anio, 1, 4)
    return cuatro - timedelta(days=(cuatro.weekday() + 1) % 7)


def semanas_del_anio(anio):
    return (inicio_semana_1(anio + 1) - inicio_semana_1(anio)).days // 7


def semana_de_fecha(dia):
    """Fecha -> (ano epidemiologico, semana). None si no hay fecha."""
    if dia is None or pd.isna(dia):
        return None
    dia = pd.Timestamp(dia).date()
    for anio in (dia.year + 1, dia.year, dia.year - 1):
        ini = inicio_semana_1(anio)
        if dia >= ini:
            return anio, (dia - ini).days // 7 + 1


def fechas_semana(anio, semana):
    ini = inicio_semana_1(anio) + timedelta(weeks=int(semana) - 1)
    return ini, ini + timedelta(days=6)


# ==========================================================
# DESCARGA
# ==========================================================

def tamano_remoto(url):
    for i in range(REINTENTOS):
        try:
            r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return int(r.headers["Content-Length"])
        except Exception as e:           # red inestable: se reintenta
            print(f"    HEAD fallo ({e}); reintento {i + 1}/{REINTENTOS}")
            time.sleep(ESPERA * 2 ** i)
    raise RuntimeError(f"No se pudo consultar {url}")


def descargar(evento, anio):
    """Baja el archivo a crudo/. Reanuda un .part y no rebaja lo que ya esta completo."""
    CRUDO.mkdir(parents=True, exist_ok=True)
    destino = CRUDO / f"Datos_{anio}_{evento}.xlsx"
    url = URL.format(anio=anio, evento=evento)
    total = tamano_remoto(url)
    if total is None:
        print(f"  {destino.name}: no existe en el portal")
        return None
    if destino.exists() and destino.stat().st_size == total:
        return destino
    parcial = destino.with_suffix(".xlsx.part")
    for i in range(REINTENTOS):
        ya = parcial.stat().st_size if parcial.exists() else 0
        if ya > total:
            parcial.unlink()
            ya = 0
        try:
            cab = {"Range": f"bytes={ya}-"} if ya else {}
            with requests.get(url, headers=cab, stream=True, timeout=TIMEOUT) as r:
                r.raise_for_status()
                if ya and r.status_code != 206:      # el servidor ignoro el rango
                    ya = 0
                with open(parcial, "ab" if ya else "wb") as f:
                    for trozo in r.iter_content(BLOQUE):
                        f.write(trozo)
            if parcial.stat().st_size == total:
                parcial.replace(destino)
                print(f"  {destino.name}: {total / 1e6:.1f} MB bajados")
                return destino
            print(f"    incompleto ({parcial.stat().st_size}/{total}); reanudo")
        except Exception as e:
            print(f"    descarga fallo ({e}); reintento {i + 1}/{REINTENTOS}")
            time.sleep(ESPERA * 2 ** i)
    raise RuntimeError(f"No se pudo bajar {url}")


# ==========================================================
# LECTURA (lista blanca en el mismo paso)
# ==========================================================

def normalizar(nombre):
    """Cabecera -> nombre canonico. 'año' llega con la enie rota segun el ano."""
    n = str(nombre).strip().lower()
    if n.startswith("a") and n.endswith("o") and len(n) in (3, 4) and n != "ano_":
        return "anio"
    return n


def columnas_conteo():
    cols = []
    for pref, (tot, _) in BLOQUES_995.items():
        cols += [f"{pref}_{i}" for i in range(1, 8)] + [tot]
    return cols


def buscar_cabecera(libro, obligatorias=("cod_pre", "semana", "tot_exturg")):
    """La hoja y la fila donde esta la cabecera de la ficha.

    El formato no es estable entre anos: 2019 trae una hoja resumen antes de la
    de datos ('Hoja1' y 'Final'), 2021 una fila de rotulos encima de la
    cabecera. Se toma la hoja con mas filas cuya cabecera, en las 10 primeras
    filas, tenga las columnas obligatorias. Solo se miran celdas de texto que
    coincidan con los nombres de la ficha: ningun valor se imprime.
    """
    mejor = None
    for nombre in libro.sheet_names:
        hoja = libro.get_sheet_by_name(nombre)
        for k, fila in enumerate(hoja.iter_rows()):
            if k >= 10:
                break
            cab = [normalizar(c) for c in fila]
            if all(o in cab for o in obligatorias):
                if mejor is None or hoja.height > mejor[2]:
                    mejor = (nombre, k, hoja.height)
                break
        del hoja
    if mejor is None:
        raise ValueError(f"ninguna hoja tiene una cabecera con {list(obligatorias)}")
    return mejor[0], mejor[1]


def leer_995(ruta):
    """Excel -> DataFrame con SOLO la lista blanca. Devuelve (tabla, descartadas, faltan)."""
    from python_calamine import CalamineWorkbook

    libro = CalamineWorkbook.from_path(str(ruta))
    nombre, fila_cab = buscar_cabecera(libro, ("cod_pre", "semana", "iracext_1", "totcext_1"))
    hoja = libro.get_sheet_by_name(nombre)
    filas = hoja.iter_rows()
    for _ in range(fila_cab):
        next(filas)
    cabecera = [normalizar(c) for c in next(filas)]
    blanca = set(IDENTIFICACION) | set(columnas_conteo()) | {"cod_dep"}
    idx = [i for i, c in enumerate(cabecera) if c in blanca]
    nombres = [cabecera[i] for i in idx]
    descartadas = [c for c in cabecera if c not in blanca]
    datos = [[f[i] if i < len(f) else None for i in idx] for f in filas]
    del filas, hoja, libro
    tabla = pd.DataFrame(datos, columns=nombres)
    del datos
    gc.collect()
    # Filas enteramente vacias al final de la hoja (formato de Excel, no datos).
    tabla = tabla[tabla["cod_pre"].astype(str).str.strip().isin(["", "None", "nan"]) == False]
    # 2012 no trae las columnas tot_*: se reconstruyen como suma de sus 7 edades,
    # que es exactamente lo que valen en los anos que si las traen (auditado).
    for pref, (tot, _) in BLOQUES_995.items():
        edades = [f"{pref}_{i}" for i in range(1, 8)]
        if tot not in tabla.columns and all(e in tabla.columns for e in edades):
            tabla[tot] = tabla[edades].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
            descartadas.append(f"({tot} reconstruida)")
    faltan = sorted((set(columnas_conteo()) | {"semana", "cod_pre", "cod_sub", "nom_upgd"})
                    - set(tabla.columns))
    return tabla, descartadas, faltan


def fecha(serie):
    """fec_not llega como fecha de Excel o como texto, y el texto en dos formatos.

    2021 la trae como texto dd/mm/aaaa. Sin formato explicito pandas la leia
    como mes/dia: el 05/01/2021 salia 1 de mayo, y solo 1 de 52 semanas caia en
    su sabado. Se prueba dd/mm/aaaa y luego aaaa-mm-dd; nunca mm/dd.
    """
    fechas = pd.to_datetime(serie.where(serie.map(lambda x: not isinstance(x, str))),
                            errors="coerce")
    # Se toma la parte antes del espacio, no los 10 primeros caracteres: con dias o
    # meses de un digito ("5/1/2021 00:00:00") el corte fijo dejaba "5/1/2021 0" y
    # la fecha se perdia (medido en las fichas individuales, 2026-09-28).
    texto = (serie.where(serie.map(lambda x: isinstance(x, str))).astype("string")
             .str.strip().str.split(" ").str[0])
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        fechas = fechas.fillna(pd.to_datetime(texto, format=formato, errors="coerce"))
    return fechas


def codigo(serie, ancho):
    """Codigos que llegan como numero (17001.0) o texto ('17001') -> texto con ceros."""
    # Algunos anos traen el codigo como texto con forma de formula: ="01".
    s = (serie.astype(str).str.strip().str.replace(r'^="?|"$', "", regex=True)
         .str.replace(r"\.0$", "", regex=True))
    return s.str.zfill(ancho)


def corregir_semanas(tabla, anio, notas):
    """Filas del ano del archivo, con la semana dentro de las que tiene ese ano."""
    notas["anio_distinto"] = int((tabla["anio"] != anio).sum())
    tabla = tabla[tabla["anio"] == anio]
    # Semana imposible para el ano (2021 trae 39 filas en la 53, y 2021 tiene 52
    # semanas: algunos calendarios internos le asignaban una 53 por error). Se
    # reasigna con la regla a partir de fec_not, que es el sabado que cierra la
    # semana notificada; si fec_not cae en otro ano, la fila se descarta.
    fuera = ~tabla["semana"].between(1, semanas_del_anio(anio))
    if fuera.any():
        por_fecha = tabla.loc[fuera, "fec_not"].map(semana_de_fecha)
        mismo = por_fecha.map(lambda x: x is not None and x[0] == anio)
        tabla.loc[mismo[mismo].index, "semana"] = por_fecha[mismo].map(lambda x: x[1])
        notas["semana_reasignada_por_fec_not"] = int(mismo.sum())
        notas["semana_reasignada_destinos"] = ",".join(
            f"{k}:{v}" for k, v in por_fecha[mismo].map(lambda x: x[1]).value_counts().items())
        otra = por_fecha[~mismo].map(lambda x: f"{x[0]}-{x[1]}" if x else "nulo")
        notas["semana_fuera_otra_fecha"] = ",".join(f"{k}:{v}" for k, v in otra.value_counts().items())
        fuera = ~tabla["semana"].between(1, semanas_del_anio(anio))
    notas["semana_fuera_de_rango"] = int(fuera.sum())
    notas["semanas_fuera_valores"] = ",".join(
        f"{int(k) if pd.notna(k) else 'nulo'}:{v}"
        for k, v in tabla.loc[fuera, "semana"].value_counts(dropna=False).items())
    tabla = tabla[~fuera].copy()
    tabla["semana"] = tabla["semana"].astype(int)
    return tabla


def limpiar_995(tabla, anio):
    """Tipos, codigos y duplicados. Devuelve (tabla, notas de auditoria)."""
    notas = {"filas_leidas": len(tabla)}
    conteo = [c for c in columnas_conteo() if c in tabla.columns]
    for c in conteo + ["semana", "anio", "ajuste"]:
        if c in tabla.columns:
            tabla[c] = pd.to_numeric(tabla[c], errors="coerce")
    if "anio" not in tabla.columns:
        tabla["anio"] = anio
    tabla["cod_pre"] = codigo(tabla["cod_pre"], 10)
    tabla["cod_sub"] = codigo(tabla["cod_sub"], 2)
    # El municipio sale de los 5 primeros digitos del codigo de la UPGD
    # (2 de departamento + 3 de municipio, segun el instructivo de la ficha),
    # que esta en todos los anos. cod_mun solo se usa para comprobarlo: en 2019
    # viene partido en cod_dep + cod_mun de 3 digitos.
    declarado = codigo(tabla["cod_mun"], 5)
    if "cod_dep" in tabla.columns:
        corto = tabla["cod_mun"].astype(str).str.replace(r"\.0$", "", regex=True).str.len() <= 3
        declarado = declarado.where(~corto, codigo(tabla["cod_dep"], 2)
                                    + codigo(tabla["cod_mun"], 3))
    tabla["cod_mun_declarado"] = declarado
    tabla["cod_mun"] = tabla["cod_pre"].str[:5]
    notas["cod_mun_distinto_del_de_la_upgd"] = int((declarado != tabla["cod_mun"]).sum())
    notas["cod_mun_distinto_mismo_departamento"] = int(
        ((declarado != tabla["cod_mun"]) & (declarado.str[:2] == tabla["cod_mun"].str[:2])).sum())
    notas["filas_manizales_por_upgd"] = int((tabla["cod_mun"] == MANIZALES).sum())
    notas["filas_manizales_por_cod_mun"] = int((declarado == MANIZALES).sum())
    tabla["upgd"] = tabla["cod_pre"] + tabla["cod_sub"]
    tabla["fec_not"] = fecha(tabla["fec_not"])
    notas["fec_not_nula"] = int(tabla["fec_not"].isna().sum())
    tabla["nom_upgd"] = tabla["nom_upgd"].astype(str).str.strip()

    tabla = corregir_semanas(tabla, anio, notas)

    # 1. Filas repetidas identicas (misma UPGD, semana y conteos): una sola.
    antes = len(tabla)
    tabla = tabla.drop_duplicates(["upgd", "semana"] + conteo)
    notas["duplicados_identicos"] = antes - len(tabla)
    # 2. Misma UPGD y semana con conteos distintos: gana el ajuste mas reciente
    #    (ajuste 7 sobre 0) y, a igualdad, la notificacion mas tardia.
    antes = len(tabla)
    tabla = (tabla.sort_values(["ajuste", "fec_not"], na_position="first")
                  .drop_duplicates(["upgd", "semana"], keep="last"))
    notas["duplicados_resueltos"] = antes - len(tabla)
    notas["conteos_nulos"] = int(tabla[conteo].isna().sum().sum())
    notas["conteos_negativos"] = int((tabla[conteo] < 0).sum().sum())

    # Coherencia de la ficha: el total del bloque es la suma de sus 7 edades.
    for pref, (tot, _) in BLOQUES_995.items():
        edades = [f"{pref}_{i}" for i in range(1, 8)]
        if tot in tabla.columns and all(e in tabla.columns for e in edades):
            notas[f"incoherente_{tot}"] = int((tabla[edades].sum(axis=1) != tabla[tot]).sum())
    notas["ira_mayor_que_total"] = int((tabla["tot_iraext"] > tabla["tot_exturg"]).sum())

    # fec_not es el ultimo dia de la semana notificada (instructivo de la ficha).
    # Su moda por semana tiene que ser el sabado que dice la regla de fechas.
    moda = tabla.groupby("semana")["fec_not"].agg(lambda s: s.mode().iloc[0] if s.notna().any() else pd.NaT)
    esperado = pd.Series({s: pd.Timestamp(fechas_semana(anio, s)[1]) for s in moda.index})
    notas["semanas"] = int(len(moda))
    notas["semanas_con_fec_not_en_sabado_esperado"] = int((moda == esperado).sum())
    return tabla, notas


def resumir_995(tabla, anio):
    """Crudo limpio -> (UPGD x semana de Caldas, semana del pais). Sin columna de persona."""
    conteo = columnas_conteo()
    # Caldas por cualquiera de los dos criterios, para poder medir el otro.
    caldas = tabla[(tabla["cod_mun"].str[:2] == CALDAS)
                   | (tabla["cod_mun_declarado"].str[:2] == CALDAS)]
    upgd = caldas[["upgd", "nom_upgd", "cod_mun", "cod_mun_declarado", "semana"] + conteo].copy()
    upgd.insert(0, "anio", anio)
    pais = tabla.groupby("semana")[conteo].sum()
    pais["n_instituciones_notificando"] = tabla.groupby("semana")["upgd"].nunique()
    pais = pais.reset_index()
    pais.insert(0, "anio", anio)
    return upgd, pais


# ----------------------------------------------------------
# 998: morbilidad por EDA, colectiva
# ----------------------------------------------------------
# Ficha FOR-R02.0000-002 V:05 (2016), compartida con varicela, chikunguna y
# 'evento sin establecer': casos por 18 grupos de edad (< 1, 1-4, 5-9, ...,
# 75-79, >= 80), sexo, clasificacion, hospitalizados y barrio. NO trae
# denominador (consultas por todas las causas), y una UPGD puede notificar
# varias filas la misma semana (una por barrio o brote). 2014 viene en otro
# formato: una tabla municipal con 'casos' y sin edad ni institucion.
EDAD_998 = ["gru_1", "gru_2"] + [f"grupo_{i}" for i in range(3, 19)]
# Los 18 grupos se agregan a las bandas del hospital (salidas/triage_edad.parquet).
BANDAS_998 = {"0_4": EDAD_998[0:2], "5_14": EDAD_998[2:4], "15_44": EDAD_998[4:10],
              "45_64": EDAD_998[10:14], "65_mas": EDAD_998[14:18]}
# bar_sector (barrio) se lee SOLO para distinguir dos brotes legitimos de una
# fila repetida, y se descarta antes de guardar nada.
ID_998 = ["semana", "anio", "fec_not", "cod_pre", "cod_sub", "cod_mun", "ajuste",
          "nom_upgd", "pte_hos", "bar_sector", "total", "total_grupos",
          "cod_dpto_n", "cod_mun_n", "casos"]


def leer_998(ruta):
    from python_calamine import CalamineWorkbook

    libro = CalamineWorkbook.from_path(str(ruta))
    try:
        nombre, fila_cab = buscar_cabecera(libro, ("cod_pre", "semana", "gru_1"))
    except ValueError:                              # 2014: tabla municipal
        nombre, fila_cab = buscar_cabecera(libro, ("semana", "cod_mun_n", "casos"))
    hoja = libro.get_sheet_by_name(nombre)
    filas = hoja.iter_rows()
    for _ in range(fila_cab):
        next(filas)
    cabecera = [normalizar(c) for c in next(filas)]
    blanca = set(ID_998) | set(EDAD_998)
    idx = [i for i, c in enumerate(cabecera) if c in blanca and c not in cabecera[:i]]
    nombres = [cabecera[i] for i in idx]
    descartadas = [c for c in cabecera if c not in blanca]
    datos = [[f[i] if i < len(f) else None for i in idx] for f in filas]
    del filas, hoja, libro
    tabla = pd.DataFrame(datos, columns=nombres)
    del datos
    gc.collect()
    municipal = "casos" in tabla.columns and "gru_1" not in tabla.columns
    necesarias = {"semana", "cod_mun_n", "casos"} if municipal else {"semana", "cod_pre", "cod_sub"} | set(EDAD_998)
    return tabla, descartadas, sorted(necesarias - set(tabla.columns))


def limpiar_998(tabla, anio):
    notas = {"filas_leidas": len(tabla)}
    municipal = "gru_1" not in tabla.columns
    notas["formato"] = "municipal_sin_edad" if municipal else "upgd_18_edades"
    for c in ["semana", "anio", "ajuste", "pte_hos", "casos", "total", "total_grupos"] + EDAD_998:
        if c in tabla.columns:
            tabla[c] = pd.to_numeric(tabla[c], errors="coerce")
    if "anio" not in tabla.columns:
        tabla["anio"] = anio
    tabla["fec_not"] = fecha(tabla["fec_not"]) if "fec_not" in tabla.columns else pd.NaT
    if municipal:
        dpto = codigo(tabla["cod_dpto_n"], 2)
        mun = codigo(tabla["cod_mun_n"], 3)
        tabla["cod_mun"] = np.where(mun.str.len() == 5, mun, dpto + mun.str[-3:])
        tabla["upgd"] = None
        tabla["nom_upgd"] = None
        tabla["casos_eda_total"] = tabla["casos"]
        for b in BANDAS_998:
            tabla[f"casos_eda_{b}"] = np.nan
        tabla["casos_eda_hospitalizados"] = np.nan
    else:
        tabla["cod_pre"] = codigo(tabla["cod_pre"], 10)
        tabla["cod_sub"] = codigo(tabla["cod_sub"], 2)
        tabla["cod_mun"] = tabla["cod_pre"].str[:5]
        tabla["upgd"] = tabla["cod_pre"] + tabla["cod_sub"]
        tabla["nom_upgd"] = tabla["nom_upgd"].astype(str).str.strip()
        tabla["casos_eda_total"] = tabla[EDAD_998].sum(axis=1, min_count=1)
        for b, cols in BANDAS_998.items():
            tabla[f"casos_eda_{b}"] = tabla[cols].sum(axis=1, min_count=1)
        tabla["casos_eda_hospitalizados"] = tabla.get("pte_hos", np.nan)
        for ref in ("total", "total_grupos"):
            if ref in tabla.columns:
                notas[f"suma_edades_distinta_de_{ref}"] = int(
                    (tabla[ref].notna() & (tabla[ref] != tabla["casos_eda_total"])).sum())
    notas["ajustes"] = ",".join(f"{k}:{v}" for k, v in tabla["ajuste"].value_counts(dropna=False).items()) \
        if "ajuste" in tabla.columns else ""
    # Ajuste 6 es 'descartado' en la codificacion del SIVIGILA: la notificacion
    # se anulo y no son casos. Solo aparece en 2013 (132 filas).
    if "ajuste" in tabla.columns:
        anulada = tabla["ajuste"] == 6
        notas["filas_ajuste_6_descartadas"] = int(anulada.sum())
        tabla = tabla[~anulada]
    tabla = corregir_semanas(tabla, anio, notas)

    # Varias filas de la misma UPGD y semana son legitimas (una por barrio o
    # brote). Solo se quita la fila repetida entera, barrio incluido.
    clave = [c for c in ["upgd", "cod_mun", "semana", "bar_sector", "ajuste", "fec_not"] + EDAD_998
             + ["casos"] if c in tabla.columns]
    # En la tabla municipal de 2014 no hay institucion ni barrio: dos filas
    # iguales son dos UPGD del mismo municipio con los mismos casos, no una
    # repeticion. Ahi no se deduplica.
    antes = len(tabla)
    if not municipal:
        tabla = tabla.drop_duplicates(clave)
    notas["duplicados_identicos"] = antes - len(tabla)
    if "bar_sector" in tabla.columns:
        tabla = tabla.drop(columns="bar_sector")
    if not municipal:
        notas["filas_por_upgd_semana_max"] = int(tabla.groupby(["upgd", "semana"]).size().max())
    notas["casos_negativos"] = int((tabla["casos_eda_total"] < 0).sum())
    notas["casos_nulos"] = int(tabla["casos_eda_total"].isna().sum())
    return tabla, notas


VARIABLES_998 = ["casos_eda_total"] + [f"casos_eda_{b}" for b in BANDAS_998] + ["casos_eda_hospitalizados"]


def resumir_998(tabla, anio):
    caldas = tabla[tabla["cod_mun"].str[:2] == CALDAS]
    upgd = caldas[["upgd", "nom_upgd", "cod_mun", "semana"] + VARIABLES_998].copy()
    upgd.insert(0, "anio", anio)
    g = tabla.groupby("semana")
    pais = g[VARIABLES_998].sum(min_count=1)
    pais["n_instituciones_notificando"] = g["upgd"].nunique() if tabla["upgd"].notna().any() else np.nan
    pais = pais.reset_index()
    pais.insert(0, "anio", anio)
    return upgd, pais


def series_998(upgd, pais, largo_995):
    """Formato largo del 998, con el denominador del 995 del mismo ambito y semana."""
    partes = []
    for ambito, sub in (("manizales", upgd[upgd["cod_mun"] == MANIZALES]),
                        ("caldas", upgd[upgd["cod_mun"].str[:2] == CALDAS])):
        g = sub.groupby(["anio", "semana"])
        suma = g[VARIABLES_998].sum(min_count=1)
        suma["n_instituciones_notificando"] = g["upgd"].nunique().replace(0, np.nan)
        partes.append((ambito, suma))
    partes.append(("colombia", pais.set_index(["anio", "semana"])))
    den = None
    if largo_995 is not None and len(largo_995):
        den = largo_995[largo_995["variable"].isin(
            ["consultas_todas_causas_total", "consultas_todas_causas_0_4"])].pivot_table(
            index=["ambito", "anio", "semana_epi"], columns="variable", values="valor")
    largo = []
    for ambito, suma in partes:
        ancho = suma.copy()
        if den is not None:
            d = den.xs(ambito, level="ambito").rename_axis(["anio", "semana"])
            ancho = ancho.join(d, how="left")
            for num, dd, nom in (("casos_eda_total", "consultas_todas_causas_total",
                                  "proporcion_eda_sobre_consultas_995_total"),
                                 ("casos_eda_0_4", "consultas_todas_causas_0_4",
                                  "proporcion_eda_sobre_consultas_995_0_4")):
                ancho[nom] = ancho[num] / ancho[dd].where(ancho[dd] > 0)
            ancho = ancho.drop(columns=["consultas_todas_causas_total", "consultas_todas_causas_0_4"])
        l = ancho.reset_index().melt(["anio", "semana"], var_name="variable", value_name="valor")
        l.insert(0, "ambito", ambito)
        largo.append(l)
    largo = pd.concat(largo, ignore_index=True).dropna(subset=["valor"])
    largo["fecha_inicio_semana"] = [fechas_semana(a, s)[0] for a, s in zip(largo["anio"], largo["semana"])]
    largo["fecha_fin_semana"] = [fechas_semana(a, s)[1] for a, s in zip(largo["anio"], largo["semana"])]
    largo.insert(0, "evento", 998)
    largo = largo.rename(columns={"semana": "semana_epi"})
    return largo[["evento", "anio", "semana_epi", "fecha_inicio_semana", "fecha_fin_semana",
                  "ambito", "variable", "valor"]]


def auditar_998(largo, notas, upgd):
    print("\n=== 998 (EDA): calidad por archivo ===")
    n = pd.DataFrame(notas).T
    cols = [c for c in ["formato", "filas_leidas", "anio_distinto", "semana_fuera_de_rango",
                        "semana_reasignada_por_fec_not", "duplicados_identicos",
                        "filas_por_upgd_semana_max", "filas_ajuste_6_descartadas", "suma_edades_distinta_de_total",
                        "suma_edades_distinta_de_total_grupos", "casos_nulos", "ajustes"]
            if c in n.columns]
    print(n[cols].to_string())
    print("columnas descartadas (solo nombres):")
    for k, v in n["descartadas"].items():
        print(f"  {k}: {v}")
    ancho = largo.pivot_table(index=["ambito", "anio", "semana_epi"], columns="variable",
                              values="valor").reset_index()
    for c in ["n_instituciones_notificando", "casos_eda_0_4", "proporcion_eda_sobre_consultas_995_total"]:
        if c not in ancho.columns:       # 2014 no trae edad ni institucion
            ancho[c] = np.nan
    print("\n=== 998 por ano ===")
    for ambito in ("manizales", "caldas", "colombia"):
        a = ancho[ancho["ambito"] == ambito].groupby("anio").agg(
            semanas=("semana_epi", "nunique"),
            inst_media=("n_instituciones_notificando", "mean"),
            casos=("casos_eda_total", "sum"), casos_0_4=("casos_eda_0_4", "sum"),
            prop_sobre_995=("proporcion_eda_sobre_consultas_995_total", "mean"))
        print(f"-- {ambito}")
        print(a.round(4).to_string())
    m = ancho[ancho["ambito"] == "manizales"].copy()
    m["mes"] = [(fechas_semana(a, s)[0] + timedelta(days=3)).month
                for a, s in zip(m["anio"], m["semana_epi"])]
    print("Manizales, casos EDA medios por semana segun el mes (sin 2020-2021):")
    print(m[~m["anio"].isin([2020, 2021])].groupby("mes")["casos_eda_total"].mean().round(0).to_frame().T.to_string())


def procesar_archivo(evento, anio, ruta):
    """Un archivo -> resumen en disco. Si el resumen es de este mismo crudo, no relee."""
    resumen = ruta.with_suffix(".resumen.parquet")
    resumen_pais = ruta.with_suffix(".pais.parquet")
    notas_ruta = ruta.with_suffix(".notas.json")
    marca = f"{ruta.stat().st_size}-{VERSION_RESUMEN[evento]}"
    if resumen.exists() and notas_ruta.exists():
        notas = json.loads(notas_ruta.read_text(encoding="utf-8"))
        if str(notas.get("tamano_crudo")) == marca:
            return pd.read_parquet(resumen), pd.read_parquet(resumen_pais), notas
    t = time.time()
    leer, limpiar, resumir = {995: (leer_995, limpiar_995, resumir_995),
                              998: (leer_998, limpiar_998, resumir_998)}[evento]
    tabla, descartadas, faltan = leer(ruta)
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas de la ficha {faltan}. "
                         f"Cabecera sin reconocer: {descartadas}")
    tabla, notas = limpiar(tabla, anio)
    upgd, pais = resumir(tabla, anio)
    del tabla
    gc.collect()
    notas.update(tamano_crudo=marca, descartadas=",".join(descartadas),
                 segundos=round(time.time() - t, 1))
    upgd.to_parquet(resumen)
    pais.to_parquet(resumen_pais)
    notas_ruta.write_text(json.dumps(notas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {ruta.name}: {notas['filas_leidas']} filas en {notas['segundos']} s")
    return upgd, pais, notas


# ==========================================================
# SERIES
# ==========================================================

def a_variables(tabla):
    """Suma de columnas de la ficha -> variables con nombre del proyecto (ancho)."""
    salida = pd.DataFrame(index=tabla.index)
    for pref, (tot, nombre) in BLOQUES_995.items():
        salida[f"{nombre}_total"] = tabla[tot]
        for i, g in enumerate(GRUPOS, start=1):
            salida[f"{nombre}_{g}"] = tabla[f"{pref}_{i}"]
        salida[f"{nombre}_0_4"] = tabla[[f"{pref}_{i}" for i in (1, 2, 3)]].sum(axis=1)
    for num, den, prop in PARES:
        sufijos = ["total", "0_4"] + GRUPOS if num == "consultas_ira" else ["total"]
        for s in sufijos:
            d = salida[f"{den}_{s}"]
            salida[f"{prop}_{s}"] = np.where(d > 0, salida[f"{num}_{s}"] / d.where(d > 0), np.nan)
    salida["n_instituciones_notificando"] = tabla["n_instituciones_notificando"]
    return salida


def series(upgd, pais, evento):
    conteo = columnas_conteo()
    partes = []
    for ambito, sub in (("manizales", upgd[upgd["cod_mun"] == MANIZALES]),
                        ("caldas", upgd[upgd["cod_mun"].str[:2] == CALDAS])):
        g = sub.groupby(["anio", "semana"])
        suma = g[conteo].sum()
        suma["n_instituciones_notificando"] = g["upgd"].nunique()
        partes.append((ambito, suma))
    partes.append(("colombia", pais.set_index(["anio", "semana"])))
    largo = []
    for ambito, suma in partes:
        ancho = a_variables(suma)
        l = ancho.reset_index().melt(["anio", "semana"], var_name="variable", value_name="valor")
        l.insert(0, "ambito", ambito)
        largo.append(l)
    largo = pd.concat(largo, ignore_index=True)
    fechas = {(a, s): fechas_semana(a, s) for a, s in largo[["anio", "semana"]].drop_duplicates().itertuples(index=False)}
    largo["fecha_inicio_semana"] = [fechas[(a, s)][0] for a, s in zip(largo["anio"], largo["semana"])]
    largo["fecha_fin_semana"] = [fechas[(a, s)][1] for a, s in zip(largo["anio"], largo["semana"])]
    largo.insert(0, "evento", evento)
    largo = largo.rename(columns={"semana": "semana_epi"})
    return largo[["evento", "anio", "semana_epi", "fecha_inicio_semana", "fecha_fin_semana",
                  "ambito", "variable", "valor"]]


def instituciones(upgd, evento):
    m = upgd[upgd["cod_mun"] == MANIZALES]
    out = pd.DataFrame({
        "evento": evento, "anio": m["anio"], "semana_epi": m["semana"],
        "cod_upgd": m["upgd"], "nombre_upgd": m["nom_upgd"],
        "consultas_ira": m["tot_iraext"], "consultas_todas_causas": m["tot_exturg"],
        "consultas_ira_0_4": m[["iracext_1", "iracext_2", "iracext_3"]].sum(axis=1),
        "consultas_todas_causas_0_4": m[["totcext_1", "totcext_2", "totcext_3"]].sum(axis=1),
        "hospitalizaciones_irag": m["tot_irag"], "hospitalizaciones_todas_causas": m["tot_cau_h"],
    })
    out.insert(3, "fecha_inicio_semana",
               [fechas_semana(a, s)[0] for a, s in zip(out["anio"], out["semana_epi"])])
    return out.sort_values(["anio", "semana_epi", "cod_upgd"])


# ==========================================================
# AUDITORIA
# ==========================================================

def auditar(largo, inst, notas):
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    ancho = largo.pivot_table(index=["ambito", "anio", "semana_epi"], columns="variable",
                              values="valor").reset_index()
    print("\n=== Calidad por archivo ===")
    n = pd.DataFrame(notas).T
    cols = ["filas_leidas", "anio_distinto", "semana_fuera_de_rango", "duplicados_identicos",
            "duplicados_resueltos", "fec_not_nula", "ira_mayor_que_total", "semanas",
            "semanas_con_fec_not_en_sabado_esperado"]
    print(n[[c for c in cols if c in n.columns]].to_string())
    print("semanas fuera de rango (valor:filas):", n["semanas_fuera_valores"].to_dict())
    mun = ["cod_mun_distinto_del_de_la_upgd", "cod_mun_distinto_mismo_departamento",
           "filas_manizales_por_upgd", "filas_manizales_por_cod_mun"]
    print(n[mun].to_string())
    inco = [c for c in n.columns if c.startswith("incoherente_")]
    print("filas con total != suma de edades:", n[inco].astype(float).sum().to_dict())
    print("columnas descartadas por archivo (solo nombres):")
    for k, v in n["descartadas"].items():
        print(f"  {k}: {v}")

    print("\n=== Por ano: Manizales / Caldas / Colombia ===")
    for ambito in ("manizales", "caldas", "colombia"):
        a = ancho[ancho["ambito"] == ambito].groupby("anio").agg(
            semanas=("semana_epi", "nunique"),
            inst_media=("n_instituciones_notificando", "mean"),
            inst_min=("n_instituciones_notificando", "min"),
            ira=("consultas_ira_total", "sum"),
            todas=("consultas_todas_causas_total", "sum"),
            prop_media=("proporcion_consultas_ira_total", "mean"),
            hosp_irag=("hospitalizaciones_irag_total", "sum"),
            uci_irag=("uci_irag_total", "sum"))
        a["prop_anual"] = a["ira"] / a["todas"]
        if ambito == "manizales":
            f = inst.groupby("anio").agg(filas=("cod_upgd", "size"), instituciones=("cod_upgd", "nunique"))
            a = f.join(a)
        print(f"-- {ambito}")
        print(a.round(4).to_string())

    m = ancho[ancho["ambito"] == "manizales"].copy()
    # Mes del miercoles de la semana: el dia central decide a que mes pertenece.
    m["mes"] = [(fechas_semana(a, s)[0] + timedelta(days=3)).month
                for a, s in zip(m["anio"], m["semana_epi"])]
    print("\n=== Estacionalidad Manizales: proporcion IRA media por mes (sin 2020-2021) ===")
    e = m[~m["anio"].isin([2020, 2021])].groupby("mes")[
        ["proporcion_consultas_ira_total", "proporcion_consultas_ira_0_4"]].mean()
    print(e.round(4).T.to_string())

    print("\n=== Instituciones de Manizales: top 10 por consultas totales 2024-2025 ===")
    r = inst[inst["anio"].isin([2024, 2025])].copy()
    r["trimestre"] = r["anio"].astype(str) + "T" + ((r["semana_epi"] - 1) // 13 + 1).clip(upper=4).astype(str)
    top = r.groupby("cod_upgd")["consultas_todas_causas"].sum().nlargest(10).index
    nombres = r.drop_duplicates("cod_upgd", keep="last").set_index("cod_upgd")["nombre_upgd"]
    tr = r[r["cod_upgd"].isin(top)].pivot_table(index="cod_upgd", columns="trimestre",
                                                  values="consultas_todas_causas", aggfunc="sum")
    tr.index = [f"{c} {nombres[c][:38]}" for c in tr.index]
    print((tr / 1000).round(1).to_string())
    print("(miles de consultas por trimestre; T4 incluye la semana 53)")
    tr_ira = r[r["cod_upgd"].isin(top)].pivot_table(index="cod_upgd", columns="trimestre",
                                                      values="consultas_ira", aggfunc="sum")
    tr_ira.index = tr.index
    print("consultas IRA (miles):")
    print((tr_ira / 1000).round(2).to_string())

    print("\n=== Instituciones con cierres a Nueva EPS (consultas todas las causas, miles) ===")
    r = inst[inst["anio"] >= 2023].copy()
    r["trimestre"] = r["anio"].astype(str) + "T" + ((r["semana_epi"] - 1) // 13 + 1).clip(upper=4).astype(str)
    patron = r"AVIDANTI|SANTA SOF|DIAGNOSTIMED"
    nombradas = r[r["nombre_upgd"].str.upper().str.contains(patron, regex=True)]
    if len(nombradas):
        tn = nombradas.pivot_table(index=["cod_upgd", "nombre_upgd"], columns="trimestre",
                                   values="consultas_todas_causas", aggfunc="sum")
        print((tn / 1000).round(2).to_string())
    tot = r.groupby("trimestre")[["consultas_todas_causas", "consultas_ira"]].sum()
    tot["n_upgd"] = r.groupby("trimestre")["cod_upgd"].nunique()
    print("Manizales, todas las UPGD:")
    print(tot.T.round(0).to_string())

    comparar_hospital(ancho)


def escalones(upgd):
    """Entradas y salidas de instituciones de Manizales, y proporcion sin las que nunca ven IRA."""
    m = upgd[upgd["cod_mun"] == MANIZALES]
    print("\n=== Escalones de cobertura en Manizales ===")
    por = m.groupby(["anio", "upgd"])[["tot_exturg", "tot_iraext"]].sum().reset_index()
    filas, previas = [], set()
    for anio, g in por.groupby("anio"):
        actuales = set(g["upgd"])
        nuevas = g[g["upgd"].isin(actuales - previas)]
        sin_ira = g[g["tot_iraext"] == 0]
        con_ira = g[g["tot_iraext"] > 0]
        filas.append({
            "anio": anio, "upgd": len(actuales),
            "nuevas": len(actuales - previas) if previas else np.nan,
            "salen": len(previas - actuales) if previas else np.nan,
            "peso_nuevas_en_total": nuevas["tot_exturg"].sum() / g["tot_exturg"].sum() if previas else np.nan,
            "upgd_sin_ninguna_ira": len(sin_ira),
            "consultas_de_upgd_sin_ira": sin_ira["tot_exturg"].sum() / g["tot_exturg"].sum(),
            "prop_ira": g["tot_iraext"].sum() / g["tot_exturg"].sum(),
            "prop_ira_solo_upgd_con_ira": con_ira["tot_iraext"].sum() / con_ira["tot_exturg"].sum(),
            "top1_peso": g["tot_exturg"].max() / g["tot_exturg"].sum(),
        })
        previas = actuales
    print(pd.DataFrame(filas).set_index("anio").round(3).to_string())


def comparar_criterio_municipio(upgd):
    """Manizales por el codigo de la UPGD (el que se usa) contra el cod_mun declarado."""
    print("\n=== Criterio de municipio: codigo de la UPGD contra cod_mun declarado ===")
    a = upgd[upgd["cod_mun"] == MANIZALES]
    b = upgd[upgd["cod_mun_declarado"] == MANIZALES]
    solo_a = upgd[(upgd["cod_mun"] == MANIZALES) & (upgd["cod_mun_declarado"] != MANIZALES)]
    solo_b = upgd[(upgd["cod_mun"] != MANIZALES) & (upgd["cod_mun_declarado"] == MANIZALES)]
    filas = []
    for anio in sorted(upgd["anio"].unique()):
        sa, sb = a[a["anio"] == anio], b[b["anio"] == anio]
        wa = sa.groupby("semana")[["tot_iraext", "tot_exturg"]].sum()
        wb = sb.groupby("semana")[["tot_iraext", "tot_exturg"]].sum()
        w = wa.join(wb, lsuffix="_upgd", rsuffix="_decl", how="outer").fillna(0)
        filas.append({
            "anio": anio, "filas_upgd": len(sa), "filas_decl": len(sb),
            "solo_upgd": int((solo_a["anio"] == anio).sum()),
            "solo_decl": int((solo_b["anio"] == anio).sum()),
            "todas_upgd": sa["tot_exturg"].sum(), "todas_decl": sb["tot_exturg"].sum(),
            "prop_upgd": sa["tot_iraext"].sum() / sa["tot_exturg"].sum(),
            "prop_decl": sb["tot_iraext"].sum() / sb["tot_exturg"].sum() if len(sb) else np.nan,
            "r_semanal_ira": w["tot_iraext_upgd"].corr(w["tot_iraext_decl"]),
        })
    print(pd.DataFrame(filas).set_index("anio").round(4).to_string())
    pares = upgd[upgd["cod_mun"] != upgd["cod_mun_declarado"]]
    pares = pares[(pares["cod_mun"] == MANIZALES) | (pares["cod_mun_declarado"] == MANIZALES)]
    print("pares (municipio de la UPGD -> cod_mun declarado) que tocan Manizales, filas:")
    print(pares.groupby(["anio", "cod_mun", "cod_mun_declarado"]).size().to_string())


def comparar_hospital(ancho):
    if not TRIAGE_EDAD.exists():
        print(f"\n(no existe {TRIAGE_EDAD}: sin comparacion con el hospital)")
        return
    t = pd.read_parquet(TRIAGE_EDAD)
    # El parquet sale de un GROUP BY, que no emite ceros: un dia sin ningun
    # triage 0-4 no tiene fila. Se pivota con TODAS las bandas para que ese dia
    # cuente como 0 y no como hueco (124 dias, casi todos de 2020-2021).
    t = t.pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").fillna(0)
    t = t.reset_index()
    # Semana epidemiologica de cada dia: el sabado que la cierra identifica la semana.
    t["fin"] = t["dia"] + pd.to_timedelta((5 - t["dia"].dt.weekday) % 7, unit="D")
    h = t.groupby("fin")[["0-4", "5-14"]].sum()
    h["dias"] = t.groupby("fin").size()
    h = h[h["dias"] == 7]
    m = ancho[ancho["ambito"] == "manizales"].copy()
    m["fin"] = [pd.Timestamp(fechas_semana(a, s)[1]) for a, s in zip(m["anio"], m["semana_epi"])]
    j = m.set_index("fin").join(h, how="inner")
    j = j[(j["anio"] >= 2020) & (j["anio"] <= 2025)]
    print(f"\n=== Hospital (triage 0-4) contra SIVIGILA Manizales, {len(j)} semanas comunes ===")
    filas = []
    for etiqueta, sub in (("2020-2025", j), ("2022-2025", j[j["anio"] >= 2022])):
        for var in ("consultas_ira_0_4", "proporcion_consultas_ira_0_4", "consultas_todas_causas_0_4"):
            x, y = sub[var].astype(float), sub["0-4"].astype(float)
            ok = (x > 0) & (y > 0)
            lx, ly = np.log(x[ok]), np.log(y[ok])
            filas.append({"periodo": etiqueta, "sivigila": var, "n": int(ok.sum()),
                          "r_nivel": np.corrcoef(x[ok], y[ok])[0, 1],
                          "r_log_dif1": np.corrcoef(lx.diff().dropna(), ly.diff().dropna())[0, 1]})
    print(pd.DataFrame(filas).round(3).to_string(index=False))
    g = j.groupby("anio")
    por_anio = pd.DataFrame({
        "semanas": g.size(),
        "r_ira_0_4": g.apply(lambda s: s["consultas_ira_0_4"].corr(s["0-4"]), include_groups=False),
        "r_prop_0_4": g.apply(lambda s: s["proporcion_consultas_ira_0_4"].corr(s["0-4"]),
                              include_groups=False)})
    print("por ano (nivel, dentro del ano):")
    print(por_anio.round(3).T.to_string())


# ==========================================================
# PRINCIPAL
# ==========================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--eventos", nargs="+", type=int, default=[995, 998])
    ap.add_argument("--desde", type=int, default=2011)
    ap.add_argument("--hasta", type=int, default=2025)
    ap.add_argument("--solo-descargar", action="store_true")
    ap.add_argument("--cabeceras", action="store_true",
                    help="imprime solo los NOMBRES de columna de cada crudo y sale")
    ap.add_argument("--sin-descargar", action="store_true",
                    help="usa solo lo que ya esta en crudo/")
    args = ap.parse_args()

    anios = range(args.desde, args.hasta + 1)
    for evento in args.eventos:
        for anio in anios:
            if args.sin_descargar:
                continue
            print(f"[{evento} {anio}] descarga")
            descargar(evento, anio)
    if args.solo_descargar:
        return

    if args.cabeceras:
        from python_calamine import CalamineWorkbook
        for evento in args.eventos:
            for anio in anios:
                ruta = CRUDO / f"Datos_{anio}_{evento}.xlsx"
                if ruta.exists():
                    libro = CalamineWorkbook.from_path(str(ruta))
                    try:
                        nombre, k = buscar_cabecera(libro, ("cod_pre", "semana"))
                    except ValueError:
                        nombre, k = buscar_cabecera(libro, ("semana",))
                    hoja = libro.get_sheet_by_name(nombre)
                    filas = hoja.iter_rows()
                    for _ in range(k):
                        next(filas)
                    cab = [normalizar(c) for c in next(filas)]
                    print(f"{ruta.name} hoja '{nombre}' fila {k} ({hoja.height} filas): {cab}")
                    del filas, hoja, libro
                    gc.collect()
        return

    def procesar(evento):
        upgds, paises, notas = [], [], {}
        for anio in anios:
            ruta = CRUDO / f"Datos_{anio}_{evento}.xlsx"
            if not ruta.exists():
                print(f"  falta {ruta.name}")
                continue
            try:
                u, p, n = procesar_archivo(evento, anio, ruta)
            except ValueError as e:          # formato no reconocido: se dice y se sigue
                print(f"  {ruta.name} NO PROCESADO: {e}")
                continue
            upgds.append(u)
            paises.append(p)
            notas[anio] = n
        if not upgds:
            return None
        return pd.concat(upgds, ignore_index=True), pd.concat(paises, ignore_index=True), notas

    # Lo que no se procesa en esta corrida se conserva del archivo anterior.
    previo = pd.read_csv(SALIDA) if SALIDA.exists() else None
    partes, r995, r998 = [], None, None
    if 995 in args.eventos:
        r995 = procesar(995)
    if r995 is not None:
        largo_995 = series(r995[0], r995[1], 995)
        partes.append(largo_995)
    else:
        largo_995 = previo[previo["evento"] == 995] if previo is not None else None
    if 998 in args.eventos:
        r998 = procesar(998)
    if r998 is not None:
        partes.append(series_998(r998[0], r998[1], largo_995))
    if not partes:
        sys.exit("Nada que procesar.")
    hechos = {int(p["evento"].iloc[0]) for p in partes}
    if previo is not None:
        partes.append(previo[~previo["evento"].isin(hechos)])
    largo = pd.concat(partes, ignore_index=True)
    largo["fecha_inicio_semana"] = pd.to_datetime(largo["fecha_inicio_semana"]).dt.date
    largo["fecha_fin_semana"] = pd.to_datetime(largo["fecha_fin_semana"]).dt.date
    largo = largo.sort_values(["evento", "ambito", "variable", "anio", "semana_epi"])
    largo.to_csv(SALIDA, index=False, float_format="%.6g")
    print(f"\n{SALIDA.name}: {len(largo)} filas; por evento: "
          + ", ".join(f"{e}: {g['anio'].min()}-{g['anio'].max()}, {g['variable'].nunique()} variables"
                      for e, g in largo.groupby("evento")))

    if r995 is not None:
        upgd, _, notas = r995
        inst = instituciones(upgd, 995)
        inst.to_csv(SALIDA_INSTITUCIONES, index=False)
        print(f"{SALIDA_INSTITUCIONES.name}: {len(inst)} filas, {inst['cod_upgd'].nunique()} instituciones")
        auditar(largo[largo["evento"] == 995], inst, notas)
        escalones(upgd)
        comparar_criterio_municipio(upgd)
    if r998 is not None:
        auditar_998(largo[largo["evento"] == 998], r998[2], r998[0])

if __name__ == "__main__":
    main()
