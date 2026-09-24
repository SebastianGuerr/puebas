# -*- coding: utf-8 -*-
"""Banco de pruebas del prompt: arreglar lo que falla SIN danar lo que ya sale bien.

    python -m NLP.banco --armar                  arma los bancos (no pisa tu revision)
    python -m NLP.banco --linea-base             como sale la version guardada
    python -m NLP.banco --evaluar                corre el prompt actual sobre los bancos
    python -m NLP.banco --evaluar --prompt NLP/prompts/v1_7.py --opcion top_k=20
    python -m NLP.banco --evaluar --rapido       20 fallos + 40 aciertos

    PARA ITERAR (minutos, no horas):
    python -m NLP.banco --oid <OID> --prompt NLP/prompts/candidato.py   una nota
    python -m NLP.banco --sonda-armar            una nota por tipo de fallo y de acierto
    python -m NLP.banco --sonda --prompt NLP/prompts/candidato.py        ~14 notas

LOS DOS BANCOS, EN NLP/salidas/banco/ (ignorado por git: lleva texto clinico)
    fallos.csv      las salidas con al menos una bandera fuerte de NLP/fidelidad.py
    aciertos.csv    una muestra estratificada de salidas sin ninguna bandera
    sospechosas.csv solo la bandera suave: para mirar, no entran a la cuenta

    Los dos traen tres columnas vacias para el revisor: veredicto (bien / mal /
    parcial), salida_esperada y comentario. Una vez revisados son trabajo humano
    y --armar se niega a pisarlos; para rehacerlos hay que pedirlo con --rehacer.

LO QUE MIDE --evaluar
    fallos     corregidas   la salida nueva ya no tiene banderas fuertes
               siguen mal   las sigue teniendo
    aciertos   iguales      la misma salida que la version de referencia
               cambiadas    distintas, pero limpias y parecidas a la referencia
               DANADAS      con banderas fuertes nuevas, o muy distintas

    Una version nueva solo es mejor si corrige fallos SIN danar aciertos. Las dos
    cifras se miran juntas; ninguna vale sola. Ver NLP/docs/EVALUACION.md.
"""
import argparse
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

from NLP import fidelidad, rutas
from NLP import modelo as motor

CARPETA = rutas.SALIDAS / "banco"
FALLOS = CARPETA / "fallos.csv"
ACIERTOS = CARPETA / "aciertos.csv"
SOSPECHOSAS = CARPETA / "sospechosas.csv"
RESULTADOS = CARPETA / "resultados"

TAMANO_ACIERTOS = 150
SEMILLA = 7
MODELO = "qwen3:8b"
TIMEOUT = 1800
REVISION = ["veredicto", "salida_esperada", "comentario"]
# Con --sin-filtros no se aplica posprocesar: se mide al modelo solo. Es la
# forma justa de comparar dos modelos; con filtros se mediria a los filtros.
SIN_FILTROS = False


# ==========================================================
# ARMAR
# ==========================================================

def _leer_notas():
    import duckdb
    ruta = rutas.BASE_VISTA if rutas.BASE_VISTA.exists() else rutas.BASE_DATOS
    con = duckdb.connect(str(ruta), read_only=True)
    try:
        return con.execute(
            "select OID, fecha_triage, frase_original, frase_procesada "
            "from nota_triage").fetchdf()
    finally:
        con.close()


def _estrato(fila):
    """La caracteristica mas dificil que tiene la nota. Asegura que el banco de
    aciertos no sean 150 'malestar general' faciles."""
    o = fidelidad.plano(fila["frase_original"])
    s = fidelidad.plano(fila["frase_procesada"]).strip()
    if s == fidelidad.SIN_MOTIVO:
        return "descarte_correcto"
    if "niega" in o:
        return "negacion"
    if re.search(r"derech|izquierd|\bizq|\bder\b", o):
        return "lateralidad"
    if re.search(r"embaraz|gestac|\bsemanas\b|\bmeses\b|nino|nina|bebe|lactante|menor", o):
        return "embarazo_o_pediatria"
    if glosario_tiene(fila["frase_original"]):
        return "coloquialismo_o_sigla"
    if len(o) > 150:
        return "nota_larga"
    if len(o) < 30:
        return "nota_corta"
    return "comun"


def glosario_tiene(original):
    halladas, _, erratas = fidelidad.glosario.buscar(original)
    return bool(halladas or erratas)


def armar(rehacer=False):
    existentes = [p for p in (FALLOS, ACIERTOS) if p.exists()]
    if existentes and not rehacer:
        print("Ya existen los bancos:")
        for p in existentes:
            print(f"   {p}")
        print("\nNo se pisan: pueden tener tu revision. Para rehacerlos: --armar --rehacer")
        return 1

    notas = _leer_notas()
    revisiones = fidelidad.revisar_corpus(
        zip(notas["OID"], notas["frase_original"], notas["frase_procesada"]))
    notas["banderas"] = notas["OID"].map(lambda o: ",".join(revisiones[o]["banderas"]))
    notas["partes_inventadas"] = notas["OID"].map(lambda o: ",".join(revisiones[o]["partes_inventadas"]))
    notas["base"] = notas["OID"].map(lambda o: revisiones[o]["base"])
    notas["fallo"] = notas["OID"].map(lambda o: fidelidad.es_fallo(revisiones[o]))

    fallos = notas[notas["fallo"]].copy()
    sospechosas = notas[~notas["fallo"] & (notas["banderas"] != "")].copy()
    limpias = notas[notas["banderas"] == ""].copy()

    # Aciertos: estratificado por dificultad, y como mucho 2 notas con la misma
    # salida para que no lo llenen las frases mas repetidas.
    limpias["estrato"] = limpias.apply(_estrato, axis=1)
    limpias = limpias.sample(frac=1, random_state=SEMILLA)
    limpias = limpias.groupby(limpias["frase_procesada"].str.lower().str.strip()).head(2)
    estratos = limpias["estrato"].unique()
    cuota = max(1, TAMANO_ACIERTOS // len(estratos))
    aciertos = limpias.groupby("estrato").head(cuota)
    faltan = TAMANO_ACIERTOS - len(aciertos)
    if faltan > 0:
        aciertos = pd.concat([aciertos, limpias.drop(aciertos.index).head(faltan)])

    CARPETA.mkdir(parents=True, exist_ok=True)
    columnas = ["OID", "fecha_triage", "frase_original", "frase_procesada",
                "banderas", "partes_inventadas", "base"]
    for tabla, ruta, extra in [(fallos, FALLOS, []), (aciertos, ACIERTOS, ["estrato"]),
                               (sospechosas, SOSPECHOSAS, [])]:
        salida = tabla[columnas + extra].rename(columns={"frase_procesada": "salida_referencia"})
        for c in REVISION:
            salida[c] = ""
        salida.sort_values("OID").to_csv(ruta, index=False, encoding="utf-8-sig")

    n = len(notas)
    print(f"Notas revisadas: {n:,}\n")
    print(f"  fallos claros       {len(fallos):5,}  ({100 * len(fallos) / n:4.1f}%)  -> {FALLOS.name}")
    print(f"  sospechosas         {len(sospechosas):5,}  ({100 * len(sospechosas) / n:4.1f}%)  -> {SOSPECHOSAS.name}")
    print(f"  limpias             {len(limpias):5,}  ({100 * len(limpias) / n:4.1f}%)")
    print(f"  muestra de aciertos {len(aciertos):5,}           -> {ACIERTOS.name}")

    print("\nFallos por bandera (una nota puede tener varias):")
    for b in fidelidad.FUERTES:
        k = fallos["banderas"].str.contains(b).sum()
        if k:
            print(f"  {b:<20}{k:5,}")
    print("\nAciertos por estrato:")
    for e, k in aciertos["estrato"].value_counts().items():
        print(f"  {e:<24}{k:4}")
    print(f"\nEn {CARPETA}. Llevan texto clinico: no salen de esta carpeta.")
    return 0


# ==========================================================
# EVALUAR
# ==========================================================

def _cargar_prompt(ruta):
    """Un archivo .py con construir(nota) y VERSION. Por defecto, el de produccion."""
    if ruta is None:
        from NLP import prompt as modulo
    else:
        ruta = Path(ruta).resolve()
        spec = importlib.util.spec_from_file_location("prompt_candidato", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    global _POSPROCESAR, _MODULO
    _MODULO = modulo
    # Si el prompt trae posprocesar(original, salida), se aplica despues del
    # modelo. Es donde viven las reglas que el modelo no consigue cumplir solo.
    _POSPROCESAR = getattr(modulo, "posprocesar", lambda original, salida: salida)
    if SIN_FILTROS:
        _POSPROCESAR = lambda original, salida: salida
    return modulo.construir, getattr(modulo, "VERSION", "produccion")


_POSPROCESAR = lambda original, salida: salida
_MODULO = None


def _parecido(a, b):
    a, b = set(fidelidad.palabras(a)), set(fidelidad.palabras(b))
    return len(a & b) / len(a | b) if a | b else 1.0


def _referencia(fila):
    """Tu salida_esperada manda sobre la guardada, si la escribiste."""
    esperada = str(fila.get("salida_esperada") or "").strip()
    if esperada and esperada.lower() != "nan":
        return esperada
    return str(fila["salida_referencia"])


def _opciones(pares):
    opciones = {}
    for par in pares or []:
        clave, valor = par.split("=", 1)
        try:
            opciones[clave] = json.loads(valor)
        except json.JSONDecodeError:
            opciones[clave] = valor
    return opciones


def evaluar(ruta_prompt=None, opciones=None, modelo=MODELO, rapido=False, nombre=None):
    if not (FALLOS.exists() and ACIERTOS.exists()):
        print("Primero: python -m NLP.banco --armar")
        return 1
    construir, version = _cargar_prompt(ruta_prompt)
    opciones = opciones or {}
    motor.verificar(modelo)

    fallos = pd.read_csv(FALLOS, encoding="utf-8-sig", dtype=str).fillna("")
    aciertos = pd.read_csv(ACIERTOS, encoding="utf-8-sig", dtype=str).fillna("")
    # Lo que el revisor marco como 'mal' en aciertos pasa a fallos, y al reves.
    mal = aciertos["veredicto"].str.lower().str.strip().isin(["mal", "parcial"])
    bien = fallos["veredicto"].str.lower().str.strip().eq("bien")
    fallos, aciertos = (pd.concat([fallos[~bien], aciertos[mal]]),
                        pd.concat([aciertos[~mal], fallos[bien]]))
    if rapido:
        fallos, aciertos = fallos.head(20), aciertos.head(40)

    etiqueta = nombre or f"{version}_{modelo.replace(':', '-')}" + (
        "_" + "_".join(f"{k}{v}" for k, v in sorted(opciones.items())) if opciones else "")
    print(f"Prompt {version}   modelo {modelo}   opciones {opciones or 'por defecto'}")
    print(f"{len(fallos)} fallos + {len(aciertos)} aciertos = {len(fallos) + len(aciertos)} llamadas\n")

    filas, tiempos = [], []
    for banco, tabla in (("fallo", fallos), ("acierto", aciertos)):
        for i, (_, fila) in enumerate(tabla.iterrows(), 1):
            inicio = time.time()
            _, respuesta = motor.generar(modelo, construir(fila["frase_original"]), TIMEOUT, opciones)
            tiempos.append(time.time() - inicio)
            nueva = _POSPROCESAR(fila["frase_original"], motor.limpiar(respuesta.get("response", "")))
            filas.append({"OID": fila["OID"], "banco": banco,
                          "frase_original": fila["frase_original"],
                          "referencia": _referencia(fila), "nueva": nueva,
                          # si se acerca a num_ctx, Ollama recorta el PRINCIPIO del
                          # prompt, que es donde estan las reglas
                          "tokens_prompt": respuesta.get("prompt_eval_count")})
            print(f"\r  {banco}s {i}/{len(tabla)}   {sum(tiempos) / len(tiempos):5.1f} s/nota",
                  end="", flush=True)
        print()

    resultado = pd.DataFrame(filas)
    revisiones = fidelidad.revisar_corpus(
        zip(resultado.index, resultado["frase_original"], resultado["nueva"]))
    resultado["banderas_nuevas"] = [",".join(revisiones[i]["banderas"]) for i in resultado.index]
    resultado["fallo_nuevo"] = [fidelidad.es_fallo(revisiones[i]) for i in resultado.index]
    resultado["parecido"] = [round(_parecido(a, b), 2)
                             for a, b in zip(resultado["referencia"], resultado["nueva"])]
    resultado["igual"] = (resultado["referencia"].map(fidelidad.plano).str.strip()
                          == resultado["nueva"].map(fidelidad.plano).str.strip())

    def estado(f):
        if f["banco"] == "fallo":
            return "corregida" if not f["fallo_nuevo"] else "sigue_mal"
        if f["igual"]:
            return "igual"
        if f["fallo_nuevo"] or f["parecido"] < 0.4:
            return "DANADA"
        return "cambiada"

    resultado["estado"] = resultado.apply(estado, axis=1)
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta = RESULTADOS / f"{etiqueta}.csv"
    resultado.to_csv(ruta, index=False, encoding="utf-8-sig")

    cuenta = resultado["estado"].value_counts()
    nf, na = len(fallos), len(aciertos)
    print(f"\nFALLOS    corregidas {cuenta.get('corregida', 0):4}/{nf}"
          f"   siguen mal {cuenta.get('sigue_mal', 0):4}")
    print(f"ACIERTOS  iguales    {cuenta.get('igual', 0):4}/{na}"
          f"   cambiadas {cuenta.get('cambiada', 0):4}   DANADAS {cuenta.get('DANADA', 0):4}")
    print(f"\n{sum(tiempos) / len(tiempos):.1f} s por nota.   Detalle: {ruta}")
    tokens = pd.to_numeric(resultado["tokens_prompt"], errors="coerce")
    ventana = motor.OPCIONES["num_ctx"] if "num_ctx" not in opciones else opciones["num_ctx"]
    if tokens.notna().any():
        print(f"Tokens del prompt: mediana {tokens.median():.0f}, maximo {tokens.max():.0f} "
              f"de {ventana}" + ("   <-- RECORTE: sube num_ctx" if tokens.max() >= ventana * 0.95 else ""))
    danadas = resultado.loc[resultado["estado"] == "DANADA", "OID"].tolist()
    if danadas:
        print(f"OIDs danados (revisar en el CSV): {', '.join(map(str, danadas[:20]))}")
    return 0


# ==========================================================
# ITERACION RAPIDA: UNA NOTA, O LA SONDA
# ==========================================================
#
# El banco completo son ~200 llamadas: horas en CPU. Para iterar sobre el prompt
# se usa en cambio:
#   --oid X    una sola nota, para ver si un cambio arregla ESE fallo
#   --sonda    una nota por tipo de fallo y una por tipo de acierto (~14), para
#              ver en cada vuelta que nada de lo que salia bien se dano
# El banco completo se corre una vez al final, antes de dar la version por buena.

SONDA = CARPETA / "sonda.csv"

_PERSONA = re.compile(
    r"\b(sr|sra|senor|senora|don|dona|hijo de|hija de|madre|padre|esposo|esposa|"
    r"acompanad[oa] (?:de|por)|traid[oa] por|remitid[oa] por|dr|dra|doctor|doctora)"
    r"(\s+\w+){1,2}", re.I)


def enmascarar(texto):
    """Lo que puede identificar a alguien, tapado antes de mostrar una nota.

    No es anonimizacion garantizada -- en texto libre no existe --, es reducir lo
    obvio: numeros largos (documentos, telefonos) y el nombre que suele seguir a
    un trato o a un parentesco. La nota entera nunca sale al chat: se describe."""
    plano_ = fidelidad.plano(texto)
    plano_ = re.sub(r"\d{5,}", "[NUM]", plano_)
    plano_ = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[FECHA]", plano_)
    # Tras una palabra que anuncia a una persona, se saltan conectores y tratos
    # ('por', 'su', 'dr', 'hija') y se tapan las siguientes palabras que no son
    # clinicas, hasta tres. La version anterior tapaba 'dr' o 'su hija' y dejaba
    # el nombre a la vista. Para mostrar se prefiere tapar de mas que de menos.
    from NLP.nube import enmascarar as _fuerte
    fichas = re.split(r"(\W+)", plano_)
    i, salida = 0, []
    while i < len(fichas):
        ficha = fichas[i]
        salida.append(ficha)
        if ficha in _DISPARO:
            j, tapadas = i + 1, 0
            while j < len(fichas) and tapadas < 3:
                f = fichas[j]
                if not f.strip() or not f.isalpha():
                    if re.search(r"[,.;:]", f):
                        break
                    salida.append(f)
                elif f in _DISPARO or f in _CONECTOR:
                    salida.append(f)
                elif f in _PARADA or _fuerte.es_clinica(f):
                    break
                else:
                    salida.append("[NOMBRE]")
                    tapadas += 1
                j += 1
            i = j
            continue
        i += 1
    return "".join(salida)


_DISPARO = set("""dr dra doctor doctora sr sra senor senora don dona hijo hija madre padre
esposo esposa companero companera acompanado acompanada traido traida remitido remitida
familiar hermano hermana abuelo abuela tio tia nieto nieta mama papa novio novia""".split())
_CONECTOR = set("por de del su sus la el con".split())
_PARADA = set("""para y que quien los las a al en se le lo refiere refiriendo consulta consultan
manifiesta paciente porque pues dice desde hace hoy ayer con quienes""".split())


def armar_sonda_a_mano(fallos_oids, aciertos_oids, etiquetas=None):
    """
    La sonda con OIDs elegidos por una persona que LEYO las notas.

    Es la forma buena. La eleccion automatica tomo el 2026-09-23 cuatro salidas
    correctas como 'fallos' ('presion alta' -> 'cifras tensionales elevadas',
    'covid-19'...): los detectores sirven para encontrar candidatos, no para
    decidir que es un fallo. Ajustar el prompt contra un falso fallo empeora lo
    que estaba bien.
    """
    etiquetas = etiquetas or {}
    todas = pd.concat([pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("")
                       for p in (FALLOS, ACIERTOS, SOSPECHOSAS) if p.exists()])
    # Las notas de familias que ningun detector marcaba al armar los bancos no
    # estan en ellos: se completan desde la base.
    base = _leer_notas().rename(columns={"frase_procesada": "salida_referencia"}).astype(str)
    base["banderas"] = ""
    todas = pd.concat([todas, base]).drop_duplicates("OID").set_index("OID")
    filas = []
    for banco, oids in (("fallo", fallos_oids), ("acierto", aciertos_oids)):
        for oid in oids:
            if oid not in todas.index:
                raise SystemExit(f"El OID {oid} no esta en los bancos")
            fila = todas.loc[oid].to_dict()
            filas.append({"OID": oid, **fila, "banco": banco,
                          "tipo": etiquetas.get(oid, fila.get("estrato") or banco)})
    pd.DataFrame(filas).to_csv(SONDA, index=False, encoding="utf-8-sig")
    print(f"Sonda a mano: {len(fallos_oids)} fallos + {len(aciertos_oids)} guardas -> {SONDA}")
    return 0


def armar_sonda(rehacer=False):
    if SONDA.exists() and not rehacer:
        print(f"Ya existe {SONDA}. Para rehacerla: --sonda-armar --rehacer")
        return 1
    fallos = pd.read_csv(FALLOS, encoding="utf-8-sig", dtype=str).fillna("")
    aciertos = pd.read_csv(ACIERTOS, encoding="utf-8-sig", dtype=str).fillna("")
    # Las banderas del CSV son las del dia en que se armo el banco; los
    # detectores mejoran despues. La sonda se elige con los de HOY, para no
    # meter como 'fallo' una salida que el detector ya sabe que esta bien.
    revisiones = fidelidad.revisar_corpus(
        zip(fallos["OID"], fallos["frase_original"], fallos["salida_referencia"]))
    fallos["banderas"] = fallos["OID"].map(lambda o: ",".join(
        b for b in revisiones[o]["banderas"] if b in fidelidad.FUERTES))
    fallos = fallos[fallos["banderas"] != ""]
    elegidas = []
    for bandera in fidelidad.FUERTES:
        # Se prefiere una nota donde ESE sea el unico fallo: asi cada prueba de la
        # sonda mide una cosa y no tres a la vez.
        solas = fallos[fallos["banderas"] == bandera]
        candidatas = solas if len(solas) else fallos[
            fallos["banderas"].str.split(",").map(lambda b: bandera in b)]
        if len(candidatas):
            fila = candidatas.sample(1, random_state=SEMILLA).iloc[0].to_dict()
            elegidas.append({**fila, "banco": "fallo", "tipo": bandera})
    for estrato, grupo in aciertos.groupby("estrato"):
        fila = grupo.sample(1, random_state=SEMILLA).iloc[0].to_dict()
        elegidas.append({**fila, "banco": "acierto", "tipo": estrato})
    sonda = pd.DataFrame(elegidas)
    sonda.to_csv(SONDA, index=False, encoding="utf-8-sig")
    print(f"Sonda: {len(sonda)} notas -> {SONDA}")
    for _, f in sonda.iterrows():
        print(f"  {f['banco']:<8}{f['tipo']:<24}OID {f['OID']}")
    return 0


def _una(fila, construir, modelo, opciones):
    """Una nota por la cadena COMPLETA (NLP/cadena.py): la misma que va a produccion,
    con filtros y segunda pasada. Con --sin-filtros, el modelo solo."""
    from NLP import cadena

    inicio = time.time()

    def generar(prompt):
        return motor.generar(modelo, prompt, TIMEOUT, opciones)[1].get("response", "")

    nueva, pasada = cadena.procesar_nota(fila["frase_original"], _MODULO, generar,
                                         filtros=not SIN_FILTROS)
    revision = fidelidad.revisar(fila["frase_original"], nueva)
    revision["pasada"] = pasada
    referencia = _referencia(fila)
    igual = fidelidad.plano(nueva).strip() == fidelidad.plano(referencia).strip()
    return nueva, revision, igual, _parecido(referencia, nueva), time.time() - inicio


def probar_oid(oid, ruta_prompt=None, opciones=None, modelo=MODELO):
    construir, version = _cargar_prompt(ruta_prompt)
    tablas = [pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("")
              for p in (FALLOS, ACIERTOS, SOSPECHOSAS) if p.exists()]
    todas = pd.concat(tablas)
    fila = todas[todas["OID"] == str(oid)]
    if fila.empty:
        # Una nota que ningun detector marco no esta en los bancos, pero puede
        # ser un fallo de una familia que los detectores todavia no ven.
        notas = _leer_notas()
        notas = notas[notas["OID"].astype(str) == str(oid)]
        if notas.empty:
            print(f"El OID {oid} no esta ni en los bancos ni en la base.")
            return 1
        fila = notas.rename(columns={"frase_procesada": "salida_referencia"}).astype(str)
        fila["banderas"] = ""
    fila = fila.iloc[0]
    nueva, revision, igual, parecido, segundos = _una(fila, construir, modelo, opciones or {})
    print(f"OID {oid}   prompt {version}   {segundos:.1f} s")
    print(f"  nota (enmascarada) {enmascarar(fila['frase_original'])}")
    print(f"  antes              {fila['salida_referencia']}   [{fila.get('banderas', '')}]")
    print(f"  ahora              {nueva}   [{','.join(revision['banderas'])}]")
    print("  -> " + ("SIGUE CON FALLO" if fidelidad.es_fallo(revision) else "sin fallo")
          + ("" if not igual else "  (igual que antes)"))
    return 0


def sonda(ruta_prompt=None, opciones=None, modelo=MODELO):
    if not SONDA.exists():
        print("Primero: python -m NLP.banco --sonda-armar")
        return 1
    construir, version = _cargar_prompt(ruta_prompt)
    tabla = pd.read_csv(SONDA, encoding="utf-8-sig", dtype=str).fillna("")
    print(f"Sonda con prompt {version}, {len(tabla)} notas\n")
    retrocesos, arreglos, pendientes, perdieron = 0, 0, 0, 0
    for _, fila in tabla.iterrows():
        nueva, revision, igual, parecido, segundos = _una(fila, construir, modelo, opciones or {})
        fallo = fidelidad.es_fallo(revision)
        if fila["banco"] == "fallo":
            estado = "pendiente" if fallo else "ARREGLADA"
            arreglos += not fallo
            pendientes += fallo
        else:
            # Retroceso es lo que SI lo es: una bandera fuerte nueva, o un descarte
            # nuevo. Un cambio de redaccion ('cifras tensionales elevadas' ->
            # 'presion arterial alta') no se castiga por parecido de palabras: se
            # muestra para que lo juzgue una persona.
            descarte_nuevo = (fidelidad.plano(nueva).strip() == fidelidad.SIN_MOTIVO
                              and fidelidad.plano(fila["salida_referencia"]).strip() != fidelidad.SIN_MOTIVO)
            perdidas = fidelidad.perdido(fila["frase_original"], fila["salida_referencia"], nueva)
            # Solo cuenta una bandera que la salida anterior NO tenia. Un detector
            # nuevo que marca algo que ya estaba mal antes no es un retroceso del
            # prompt ('creo que tengo la presion alta' ya perdia la duda en v1.6).
            antes = {b for b in fidelidad.revisar(fila["frase_original"], fila["salida_referencia"])["banderas"]
                     if b in fidelidad.FUERTES}
            ahora = {b for b in revision["banderas"] if b in fidelidad.FUERTES}
            danada = bool(ahora - antes) or descarte_nuevo
            if danada:
                estado = "RETROCESO"
            elif perdidas:
                estado = "PERDIO " + ",".join(perdidas)[:12]
                perdieron += 1
            else:
                estado = "igual" if igual else "revisar"
            retrocesos += danada
        referencia = "" if igual else f"   (antes: {fila['salida_referencia'][:50]})"
        pasada = revision.get("pasada", "primera")
        marca = "" if pasada == "primera" else f" <{pasada}>"
        print(f"  {estado:<16}{fila['tipo']:<26}{nueva[:60]}{marca}{referencia}")
    print(f"\nfallos arreglados {arreglos}   pendientes {pendientes}   RETROCESOS {retrocesos}"
          f"   perdieron detalle {perdieron}")
    return 0 if retrocesos == 0 else 2


def linea_base():
    """Las banderas de la version guardada sobre los mismos bancos, sin llamar al modelo."""
    for ruta in (FALLOS, ACIERTOS):
        tabla = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str).fillna("")
        revisadas = tabla["veredicto"].str.strip().ne("").sum()
        print(f"{ruta.name:<14}{len(tabla):5} notas   revisadas por ti: {revisadas}")
        if revisadas:
            print("   " + ", ".join(f"{k}: {v}" for k, v in
                                    tabla["veredicto"].str.lower().value_counts().items() if k))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m NLP.banco")
    parser.add_argument("--armar", action="store_true")
    parser.add_argument("--rehacer", action="store_true")
    parser.add_argument("--linea-base", action="store_true")
    parser.add_argument("--evaluar", action="store_true")
    parser.add_argument("--prompt", default=None, help="archivo .py con construir() y VERSION")
    parser.add_argument("--modelo", default=MODELO)
    parser.add_argument("--opcion", action="append", metavar="CLAVE=VALOR",
                        help="parametro de Ollama, repetible: --opcion top_k=20")
    parser.add_argument("--rapido", action="store_true")
    parser.add_argument("--nombre", default=None)
    parser.add_argument("--sonda-armar", action="store_true")
    parser.add_argument("--sonda", action="store_true")
    parser.add_argument("--oid", default=None)
    parser.add_argument("--sin-filtros", action="store_true",
                        help="no aplica posprocesar: mide al MODELO solo, para comparar modelos")
    args = parser.parse_args(argv)
    global SIN_FILTROS
    SIN_FILTROS = args.sin_filtros

    if args.sonda_armar:
        return armar_sonda(args.rehacer)
    if args.sonda:
        return sonda(args.prompt, _opciones(args.opcion), args.modelo)
    if args.oid:
        return probar_oid(args.oid, args.prompt, _opciones(args.opcion), args.modelo)
    if args.armar:
        return armar(args.rehacer)
    if args.linea_base:
        return linea_base()
    if args.evaluar:
        return evaluar(args.prompt, _opciones(args.opcion), args.modelo, args.rapido, args.nombre)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
