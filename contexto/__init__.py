"""
Orquestador del contexto externo de M3s: corre los actualizadores de cada fuente según su frecuencia, deja
la frescura de cada una y el contexto diario calculado con las funciones del modelo.

    python -m contexto                  corre los pasos que tocan (frecuencia y última corrida exitosa)
    python -m contexto --todo           fuerza todos
    python -m contexto --solo sismos    uno (o varios: --solo sismos desastres)
    python -m contexto --sin-hospital   sin la extracción de SQL Server
    python -m contexto --estado         solo imprime la frescura, sin correr ni escribir nada
    python -m contexto --esperar 90     espera (hasta 90 min) a que haya terminado la corrida de hoy

Qué escribe, todo en salidas/contexto/:
    pasos.json             la última corrida de cada paso y la última exitosa (de ahí sale qué toca)
    registro/<fecha>.log   la salida completa de cada paso, con cabecera
    frescura.csv           una fila por fuente: último dato real, atraso, umbral y nivel (lo lee operacion/)
    contexto_diario.csv    una fila por día con las columnas de mecanismos.columnas, el festivo y los regímenes

El porqué de cada paso, de cada umbral y qué hacer cuando algo se pone en rojo: contexto/docs/CONTEXTO_EXTERNO.md.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
_VENV = RAIZ / ".venv" / "Scripts" / "python.exe"
PY = str(_VENV if _VENV.exists() else Path(sys.executable))
SALIDA = RAIZ / "salidas" / "contexto"
PASOS_JSON = SALIDA / "pasos.json"
REGISTRO = SALIDA / "registro"
FRESCURA = SALIDA / "frescura.csv"
DIARIO = SALIDA / "contexto_diario.csv"
BLOQUEO = SALIDA / ".bloqueo"

# El esquema de frescura.csv es FIJO: lo lee operacion/ (otro agente). No cambiar nombres ni orden.
COLUMNAS_FRESCURA = ["fuente", "archivo", "ultimo_dato", "ultima_corrida", "resultado", "dias_atraso",
                     "atraso_tolerado", "nivel", "usa_m3s", "detalle"]
VENTANA_POR_CONFIRMAR = 60          # días hacia adelante en los que un pendiente de la lista pone la fila en amarillo
CREATE_NO_WINDOW = 0x08000000       # que ningún subproceso abra una consola (la tarea vieja murió al cerrar una)

DIARIA, SEMANAL, MENSUAL = 1, 7, 30
NOMBRE_FRECUENCIA = {DIARIA: "diaria", SEMANAL: "semanal", MENSUAL: "mensual"}


# ====================================================================== pasos
@dataclass
class Paso:
    nombre: str
    comandos: list                  # cada uno, los argumentos tras el intérprete; se corren en orden y paran al fallar
    frecuencia: int                 # días entre corridas exitosas
    usa_m3s: bool                   # si falla, el orquestador sale con 1
    salidas: tuple                  # archivos o patrones glob (relativos a RAIZ) para distinguir ok de sin_cambios
    depende: tuple = ()             # si uno de estos falló en esta corrida, este paso no corre
    limite: int = 600               # segundos por comando
    requiere: str | None = None     # si este script no existe, el paso queda «omitido: no instalado»
    porque: str = ""


PASOS = [
    Paso("festivos", [["calendarios/calendario_colombia.py"]], MENSUAL, True,
         ("calendarios/calendario_Colombia.csv",), limite=300,
         porque="determinista; se corre para que avise si alguien acorta el horizonte (hoy 2030)"),
    Paso("clima_fuentes", [["calendarios/clima/clima_manizales.py"]], DIARIA, False,
         ("calendarios/clima/raw_openmeteo.csv", "calendarios/clima/raw_nasapower.csv",
          "calendarios/clima/raw_iem_skmz.csv", "calendarios/clima/clima_manizales_2020_hoy.csv"), limite=900,
         porque="Open-Meteo, NASA POWER y el METAR de La Nubia; lo usa M3 (1-7 días), no M3s"),
    Paso("clima_ideam", [["calendarios/clima/clima_ideam.py"]], DIARIA, False,
         ("calendarios/clima/clima_ideam.csv",), limite=900, requiere="calendarios/clima/clima_ideam.py",
         porque="pluviómetro y temperatura de La Nubia (datos.gov.co); el actualizador lo escribe otro agente"),
    Paso("clima_unificado", [["calendarios/clima/clima_unificado.py"]], DIARIA, False,
         ("calendarios/clima_unificado.csv.gz",), depende=("clima_fuentes", "clima_ideam"), limite=600,
         porque="consenso de las cuatro fuentes; tiene que correr después de ellas"),
    Paso("clima_completo", [["calendarios/clima/clima_completo.py"]], DIARIA, False,
         ("calendarios/clima_completo.csv.gz",), limite=900,
         porque="ERA5 de Open-Meteo; M3s no usa sus valores (quita el clima de rezago corto), pero "
                "mecanismos.columnas lee el archivo"),
    Paso("enso", [["calendarios/clima/enso.py"]], SEMANAL, True, ("calendarios/enso_oni.csv",), limite=300,
         porque="la NOAA publica el ONI una vez al mes; semanal basta para no perderlo más de una semana"),
    Paso("sismos", [["calendarios/fenomenos/sismos_usgs.py"]], DIARIA, True, ("calendarios/sismos_usgs.csv",),
         limite=300, porque="sismo_fuerte_7d es una ventana de 7 días: un día de retraso ya es 1/7 del efecto"),
    Paso("desastres", [["calendarios/fenomenos/actualizar_desastres.py"]], DIARIA, True,
         ("calendarios/desastres_manizales_2020_2026.csv", "salidas/contexto/por_confirmar_desastres.csv"),
         depende=("sismos",), limite=300,
         porque="detector preregistrado de terremotos con afectación; después de sismos"),
    Paso("mindefensa", [["calendarios/seguridad/mindefensa.py"]], SEMANAL, True,
         ("calendarios/seguridad_mindefensa.csv.gz",), limite=900,
         porque="publica mensual con 2-6 semanas de rezago; semanal recoge la publicación sin esperar un mes"),
    Paso("capturas", [["calendarios/capturas.py"]], SEMANAL, True,
         ("calendarios/vigilancia/powerbi/20*/*", "calendarios/capturas/bdua/*", "calendarios/capturas/afiliacion/*",
          "calendarios/capturas/medidas/*/*", "calendarios/capturas/oni/*", "calendarios/enso_oni.csv"), limite=2400,
         porque="Power BI del INS (semanal), BDUA, afiliación, medidas de la Supersalud y ONI: fuentes que "
                "sobrescriben su estado y solo existen si se guardan ese día"),
    Paso("sivigila", [["calendarios/vigilancia/sivigila.py"]], MENSUAL, True,
         ("calendarios/vigilancia_sivigila.csv.gz", "calendarios/vigilancia_sivigila_instituciones.csv.gz"),
         limite=2400, porque="microdatos anuales del INS (~8 meses tarde): mensual sobra para enterarse"),
    Paso("sivigila_eventos", [["calendarios/vigilancia/eventos.py", "--descargar", "--seleccionados", "--ultimos", "1"],
                              ["calendarios/vigilancia/eventos.py"]], MENSUAL, True,
         ("calendarios/vigilancia_sivigila_eventos.csv.gz", "calendarios/vigilancia_sivigila_eventos_censo.csv"),
         limite=2400, porque="eventos individuales (violencias, salud mental...), mismo ritmo que el anterior"),
    Paso("eventos", [["calendarios/eventos/actualizar_eventos.py"]], SEMANAL, True,
         ("calendarios/eventos_manizales_2020_2026.csv", "salidas/contexto/por_confirmar_eventos.csv"), limite=300,
         porque="proyecta los eventos recurrentes; semanal para que la lista por confirmar no envejezca"),
    Paso("fiestas", [["calendarios/eventos/actualizar_fiestas.py"]], SEMANAL, True,
         ("calendarios/fiestas_caldas_2020_2026.csv", "salidas/contexto/por_confirmar_eventos.csv"), limite=300,
         porque="lo mismo para las fiestas de Caldas (fut_m_fiesta_lejana)"),
    Paso("escolar", [["calendarios/actualizar_escolar.py"]], MENSUAL, False,
         ("calendarios/calendario_escolar_manizales.csv", "salidas/contexto/por_confirmar_escolar.csv"), limite=300,
         porque="recesos escolares estimados; el modelo no lo usa todavía"),
    Paso("hospital", [["-m", "extraccion", "--series"]], DIARIA, True,
         ("salidas/triage_diario.parquet", "salidas/triage_horario.parquet", "salidas/triage_entidad.parquet",
          "salidas/ingresos_entidad.parquet", "salidas/turnos_triage.parquet"), limite=3600,
         porque="conteos agregados de SQL Server (autenticación de Windows): el desenlace y la red de urgencias"),
]
POR_NOMBRE = {p.nombre: p for p in PASOS}


# ====================================================================== estado (pasos.json)
def cargar_estado() -> dict:
    if PASOS_JSON.exists():
        try:
            return json.loads(PASOS_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"pasos": {}, "orquestador": {}}


def guardar_estado(estado: dict) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    tmp = PASOS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, PASOS_JSON)


def _fecha(iso):
    return pd.Timestamp(iso).normalize() if iso else None


def toca(paso: Paso, estado: dict, hoy: pd.Timestamp) -> tuple[bool, str]:
    """Toca si nunca hubo una corrida exitosa o si la última tiene al menos `frecuencia` días."""
    ex = _fecha(estado["pasos"].get(paso.nombre, {}).get("ultima_exitosa"))
    if ex is None:
        return True, "sin corrida exitosa registrada"
    dias = (hoy.normalize() - ex).days
    if dias >= paso.frecuencia:
        return True, f"última exitosa hace {dias} d (frecuencia {NOMBRE_FRECUENCIA[paso.frecuencia]})"
    return False, f"última exitosa hace {dias} d; toca a los {paso.frecuencia}"


# ====================================================================== huella de las salidas
def _contenido(ruta: Path) -> bytes:
    """Lo que se compara para decidir ok o sin_cambios: el contenido, no la fecha del archivo. En los .gz, descomprimido
    (la cabecera gzip lleva la hora). En los CSV, las filas ordenadas: actualizar_eventos.py y actualizar_fiestas.py
    reescriben cada uno su parte de por_confirmar_eventos.csv y el orden de las filas alterna sin que cambie nada."""
    b = ruta.read_bytes()
    if ruta.name.endswith(".gz"):
        try:
            b = gzip.decompress(b)
        except OSError:
            pass
    b = b.replace(b"\r\n", b"\n")
    if ".csv" in ruta.name:
        b = b"\n".join(sorted(b.split(b"\n")))
    return b


def huella(paso: Paso) -> dict:
    h = {}
    for patron in paso.salidas:
        rutas = sorted(RAIZ.glob(patron)) if any(c in patron for c in "*?[") else [RAIZ / patron]
        for r in rutas:
            if r.is_file():
                h[str(r.relative_to(RAIZ))] = hashlib.sha256(_contenido(r)).hexdigest()
    return h


# ====================================================================== correr
def _log_del_dia(hoy: pd.Timestamp) -> Path:
    REGISTRO.mkdir(parents=True, exist_ok=True)
    return REGISTRO / f"{hoy:%Y-%m-%d}.log"


def _escribir_log(log: Path, texto: str) -> None:
    with open(log, "a", encoding="utf-8") as f:
        f.write(texto)


def _matar_arbol(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, creationflags=CREATE_NO_WINDOW)


def _ultima_linea(texto: str) -> str:
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    return lineas[-1][:300] if lineas else ""


def correr_comando(args: list, log: Path, limite: int) -> tuple[int | None, str]:
    """Corre `python <args>` desde la raíz, sin ventana, con su salida al log del día. Devuelve (código, texto)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    inicio = log.stat().st_size if log.exists() else 0
    _escribir_log(log, f"$ {Path(PY).name} {' '.join(args)}\n")
    with open(log, "ab") as salida:
        p = subprocess.Popen([PY, *args], cwd=RAIZ, stdout=salida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             env=env, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            codigo = p.wait(timeout=limite)
        except subprocess.TimeoutExpired:
            _matar_arbol(p.pid) if os.name == "nt" else p.kill()
            p.wait()
            codigo = None
    with open(log, "rb") as f:
        f.seek(inicio)
        texto = f.read().decode("utf-8", errors="replace")
    return codigo, texto


def correr_paso(paso: Paso, log: Path) -> dict:
    """Corre los comandos del paso. resultado: ok | sin_cambios | fallo | omitido."""
    t0 = time.time()
    inicio = datetime.now().isoformat(timespec="seconds")
    if paso.requiere and not (RAIZ / paso.requiere).exists():
        _escribir_log(log, f"\n==== {inicio} {paso.nombre}: omitido, no existe {paso.requiere}\n")
        return dict(inicio=inicio, resultado="omitido", codigo=None, duracion_s=0.0,
                    detalle=f"no instalado: falta {paso.requiere}")
    _escribir_log(log, f"\n==== {inicio} {paso.nombre} ====\n")
    antes = huella(paso)
    codigo, texto = 0, ""
    for args in paso.comandos:
        codigo, texto = correr_comando(args, log, paso.limite)
        if codigo != 0:
            break
    dur = round(time.time() - t0, 1)
    if codigo is None:
        res, det = "fallo", f"superó el tiempo límite de {paso.limite} s; se mató el proceso y sus hijos"
    elif codigo != 0:
        res, det = "fallo", f"código {codigo}: {_ultima_linea(texto)}"
    else:
        cambiados = [k for k, v in huella(paso).items() if antes.get(k) != v]
        res = "ok" if cambiados else "sin_cambios"
        det = (f"cambió: {', '.join(Path(c).name for c in cambiados[:4])}"
               f"{f' y {len(cambiados) - 4} más' if len(cambiados) > 4 else ''}" if cambiados
               else "ninguna salida cambió") + (f" | {_ultima_linea(texto)}" if _ultima_linea(texto) else "")
    _escribir_log(log, f"---- {paso.nombre}: {res} en {dur} s ({det})\n")
    return dict(inicio=inicio, resultado=res, codigo=codigo, duracion_s=dur, detalle=det)


def registrar(estado: dict, nombre: str, r: dict) -> None:
    e = estado["pasos"].setdefault(nombre, {})
    e["ultimo"] = r
    if r["resultado"] in ("ok", "sin_cambios"):
        e["ultima_exitosa"] = r["inicio"]


# ====================================================================== bloqueo (una corrida a la vez)
class Ocupado(RuntimeError):
    pass


class Bloqueo:
    """Bloqueo de archivo que el sistema suelta solo si el proceso muere: no queda un candado huérfano."""

    def __enter__(self):
        SALIDA.mkdir(parents=True, exist_ok=True)
        self.f = open(BLOQUEO, "a+")
        try:
            import msvcrt
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:                                   # fuera de Windows
            import fcntl
            try:
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.f.close(); raise Ocupado("hay otra corrida del orquestador en curso")
        except OSError:
            self.f.close()
            raise Ocupado("hay otra corrida del orquestador en curso")
        return self

    def __exit__(self, *exc):
        try:
            import msvcrt
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        except (ImportError, OSError):
            pass
        self.f.close()


def libre() -> bool:
    try:
        with Bloqueo():
            return True
    except Ocupado:
        return False


def esperar(minutos: float, avisar=print) -> int:
    """Espera a que haya terminado una corrida del orquestador HOY y no haya otra en curso. Para la operación semanal,
    que no debe leer los parquet mientras la extracción los escribe. 0 = listo; 3 = se agotó la espera."""
    fin = time.time() + minutos * 60
    hoy = pd.Timestamp.now().normalize()
    while True:
        o = cargar_estado().get("orquestador", {})
        termino_hoy = o.get("fin") and _fecha(o["fin"]) == hoy
        if termino_hoy and libre():
            avisar(f"contexto: la corrida de hoy terminó a las {o['fin'][11:16]} (código {o.get('codigo')})")
            return 0
        if time.time() > fin:
            avisar(f"contexto: tras {minutos:g} min no hay corrida terminada hoy; se sigue con lo que haya")
            return 3
        time.sleep(30)


# ====================================================================== frescura
def _csv_max(rel, fecha="fecha", col=None, filtro=None):
    ruta = RAIZ / rel
    usar = [fecha] + ([col] if col else []) + (list(filtro) if filtro else [])
    d = pd.read_csv(ruta, usecols=lambda c: c in usar)
    if col:
        d = d[d[col].notna()]
    if filtro:
        for c, valores in filtro.items():
            d = d[d[c].isin(valores)]
    return pd.to_datetime(d[fecha], errors="coerce").max()


def _semana_epi_fin(anio, semana):
    e4 = pd.Timestamp(year=int(anio), month=1, day=4)
    inicio = e4 - pd.Timedelta(days=(e4.dayofweek + 1) % 7) + pd.Timedelta(weeks=int(semana) - 1)
    return inicio + pd.Timedelta(days=6)                      # sábado que cierra la semana epidemiológica


def _powerbi():
    fotos = sorted(p for p in (RAIZ / "calendarios/vigilancia/powerbi").glob("20*") if p.is_dir())
    t = pd.read_csv(fotos[-1] / "ira_995_tablero.csv", usecols=["anio", "semana"]).dropna()
    a, s = t.sort_values(["anio", "semana"]).iloc[-1]
    return _semana_epi_fin(a, s)


def _bdua():
    cortes = [re.search(r"(\d{4}-\d{2}-\d{2})", p.name) for p in (RAIZ / "calendarios/capturas/bdua").glob("*.csv.gz")]
    return max(pd.Timestamp(m.group(1)) for m in cortes if m)


_MES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10,
        "nov": 11, "dic": 12}


def _afiliacion():
    fechas = []
    for p in (RAIZ / "calendarios/capturas/afiliacion").glob("*.csv.gz"):
        m = re.search(r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*-?(\d{4})", p.name.lower())
        if m:
            fechas.append(pd.Timestamp(int(m.group(2)), _MES[m.group(1)], 1) + pd.offsets.MonthEnd(0))
    return max(fechas)


def _medidas():
    """La Supersalud solo publica las medidas vigentes: el último dato es el último día en que se verificó (registro)."""
    r = pd.read_csv(RAIZ / "calendarios/capturas/registro.csv")
    r = r[r.fuente.eq("medidas") & r.accion.isin(["nuevo", "sin_cambios"])]
    return pd.to_datetime(r.fecha_hora).max().normalize()


def _hospital():
    return pd.to_datetime(pd.read_parquet(RAIZ / "salidas/triage_diario.parquet", columns=["dia"]).dia).max()


def _anio_max(rel, col="anio"):
    return pd.read_csv(RAIZ / rel, usecols=[col])[col].max()


@dataclass
class Fuente:
    fuente: str
    paso: str | None
    archivo: str
    leer: object                    # () -> Timestamp: la fecha más reciente con dato real, leída del archivo
    tolerado: int | None            # días; negativo = días de cobertura hacia adelante que tiene que tener
    aviso: int | None               # días; por encima, amarillo
    usa_m3s: bool
    nota: str = ""


EST = {"estado": ["realizado", "programado"]}
FUENTES = [
    Fuente("festivos", "festivos", "calendarios/calendario_Colombia.csv", lambda: _csv_max("calendarios/calendario_Colombia.csv"),
           -365, -730, True, "calendario: el atraso negativo es la cobertura hacia adelante"),
    Fuente("clima_openmeteo", "clima_fuentes", "calendarios/clima/raw_openmeteo.csv",
           lambda: _csv_max("calendarios/clima/raw_openmeteo.csv", col="om_temperature_2m_mean"), 10, 8, False,
           "ERA5-Land: ~5-7 días de rezago"),
    Fuente("clima_nasapower", "clima_fuentes", "calendarios/clima/raw_nasapower.csv",
           lambda: _csv_max("calendarios/clima/raw_nasapower.csv", col="np_T2M"), 10, 7, False, "~3-4 días de rezago"),
    Fuente("clima_iem", "clima_fuentes", "calendarios/clima/raw_iem_skmz.csv",
           lambda: _csv_max("calendarios/clima/raw_iem_skmz.csv", col="iem_tmax_c"), 3, 2, False,
           "METAR de La Nubia, tiempo real"),
    Fuente("clima_ideam", "clima_ideam", "calendarios/clima/clima_ideam.csv",
           lambda: _csv_max("calendarios/clima/clima_ideam.csv", col="temp_media"), 15, 10, False,
           "datos.gov.co publica La Nubia al día anterior"),
    Fuente("clima_unificado", "clima_unificado", "calendarios/clima_unificado.csv.gz",
           lambda: _csv_max("calendarios/clima_unificado.csv.gz", col="temp_media_consenso"), 10, 8, False,
           "consenso; hereda el rezago de sus fuentes"),
    Fuente("clima_completo", "clima_completo", "calendarios/clima_completo.csv.gz",
           lambda: _csv_max("calendarios/clima_completo.csv.gz", col="temperature_2m_mean"), 10, 8, False,
           "ERA5: ~6 días de rezago; indirecto en M3s (se lee, sus valores no entran)"),
    Fuente("enso", "enso", "calendarios/enso_oni.csv", lambda: _csv_max("calendarios/enso_oni.csv", col="oni"), 95, 80,
           True, "fecha = mes central del trimestre; la NOAA lo publica ~5 semanas después de ese mes"),
    Fuente("sismos", "sismos", "calendarios/sismos_usgs.csv", lambda: _csv_max("calendarios/sismos_usgs.csv"), 260,
           None, True, "catálogo de eventos: el atraso es el tiempo desde el último sismo (máximo hueco 2010-2026: 258 d)"),
    Fuente("desastres", "desastres", "calendarios/desastres_manizales_2020_2026.csv",
           lambda: _csv_max("calendarios/desastres_manizales_2020_2026.csv", fecha="fecha_inicio"), None, None, True,
           "catálogo de eventos raros: el atraso no mide frescura; manda la última corrida"),
    Fuente("mindefensa", "mindefensa", "calendarios/seguridad_mindefensa.csv.gz",
           lambda: _csv_max("calendarios/seguridad_mindefensa.csv.gz"), 75, 42, True,
           "publica por mes con 2-6 semanas de rezago; M3s lee el dato de hace 42 días: por encima, la columna queda vacía"),
    Fuente("powerbi", "capturas", "calendarios/vigilancia/powerbi/<última>/ira_995_tablero.csv", _powerbi, 24, 17, True,
           "INS semanal, ~1-2 semanas de rezago, captura semanal"),
    Fuente("bdua", "capturas", "calendarios/capturas/bdua/", _bdua, 45, 35, False, "foto mensual sin histórico"),
    Fuente("afiliacion", "capturas", "calendarios/capturas/afiliacion/", _afiliacion, 60, 50, False,
           "MinSalud: el mes M sale ~2 semanas después de cerrar"),
    Fuente("medidas", "capturas", "calendarios/capturas/registro.csv (medidas)", _medidas, 14, 9, True,
           "solo publica lo vigente: el último dato es la última verificación"),
    Fuente("sivigila", "sivigila", "calendarios/vigilancia_sivigila.csv.gz",
           lambda: _csv_max("calendarios/vigilancia_sivigila.csv.gz", fecha="fecha_fin_semana"), 640, 610, True,
           "microdatos anuales: el año Y sale ~8 meses después de cerrar"),
    Fuente("sivigila_eventos", "sivigila_eventos", "calendarios/vigilancia_sivigila_eventos.csv.gz",
           lambda: _csv_max("calendarios/vigilancia_sivigila_eventos.csv.gz", fecha="fecha_fin_semana"), 640, 610, True,
           "igual que sivigila"),
    Fuente("eventos", "eventos", "calendarios/eventos_manizales_2020_2026.csv",
           lambda: _csv_max("calendarios/eventos_manizales_2020_2026.csv", fecha="fecha_inicio", filtro=EST), -180, -365,
           True, "calendario: el atraso negativo es la cobertura hacia adelante"),
    Fuente("fiestas", "fiestas", "calendarios/fiestas_caldas_2020_2026.csv",
           lambda: _csv_max("calendarios/fiestas_caldas_2020_2026.csv", fecha="fecha_inicio", filtro=EST), -180, -365,
           True, "calendario: el atraso negativo es la cobertura hacia adelante"),
    Fuente("escolar", "escolar", "calendarios/calendario_escolar_manizales.csv",
           lambda: _csv_max("calendarios/calendario_escolar_manizales.csv", fecha="fecha_fin"), -180, -365, False,
           "calendario: el atraso negativo es la cobertura hacia adelante"),
    Fuente("hospital", "hospital", "salidas/triage_diario.parquet", _hospital, 4, 2, True,
           "extracción diaria; el último día viene a medias (la operación lo descarta)"),
    Fuente("contexto_diario", None, "salidas/contexto/contexto_diario.csv",
           lambda: _csv_max("salidas/contexto/contexto_diario.csv"), -180, -365, True,
           "salida del orquestador: si falla, las funciones de M3s no corren con los archivos de hoy"),
]


def _leer_csv_texto(ruta):
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(ruta, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(ruta, encoding="utf-8", encoding_errors="replace")


def por_confirmar(hoy: pd.Timestamp, ventana: int = VENTANA_POR_CONFIRMAR) -> dict:
    """Los pendientes de salidas/contexto/por_confirmar_*.csv que caen en [hoy, hoy + ventana]. En desastres, las
    detecciones nuevas (estado nueva_*) de los últimos `ventana` días: su efecto en el modelo va hacia adelante."""
    hoy = hoy.normalize(); fin = hoy + pd.Timedelta(days=ventana)
    items, errores, archivos = [], [], sorted(SALIDA.glob("por_confirmar_*.csv"))
    for f in archivos:
        try:
            d = _leer_csv_texto(f)
            if "fecha_estimada" in d:                                     # eventos y fiestas
                fe = pd.to_datetime(d.fecha_estimada, errors="coerce")
                m = fe.between(hoy, fin)                                  # (assign sobre una tabla vacía la rellena)
                for _, r in d[m].assign(_f=fe[m]).sort_values("_f").iterrows():
                    mun = f", {r.municipio}" if isinstance(r.get("municipio"), str) and r.municipio != "Manizales" else ""
                    items.append((r._f, f"{r.evento}{mun} {r._f:%Y-%m-%d} [{r.tipo}]"))
            elif "anio_lectivo" in d:                                     # calendario escolar
                fe = pd.to_datetime(d.fecha_inicio, errors="coerce")
                m = fe.between(hoy, fin)
                for _, r in d[m].assign(_f=fe[m]).iterrows():
                    items.append((r._f, f"receso escolar {r.tipo} {r._f:%Y-%m-%d} [estimada]"))
            elif "usgs_id" in d:                                          # desastres
                fe = pd.to_datetime(d.fecha, errors="coerce")
                m = d.estado.astype(str).str.startswith("nueva_") & fe.between(hoy - pd.Timedelta(days=ventana), hoy)
                for _, r in d[m].assign(_f=fe[m]).iterrows():
                    items.append((r._f, f"terremoto {r._f:%Y-%m-%d} M{r.magnitud} [{r.estado}]"))
        except Exception as e:                                            # noqa: BLE001
            errores.append(f"{f.name}: {e}")
    items.sort(key=lambda x: x[0])
    mt = max((datetime.fromtimestamp(f.stat().st_mtime) for f in archivos), default=None)
    return dict(n=len(items), proximo=items[0][0] if items else None, items=[t for _, t in items], errores=errores,
                actualizado=mt)


def frescura(estado: dict | None = None, hoy: pd.Timestamp | None = None) -> pd.DataFrame:
    estado = estado or cargar_estado()
    hoy = (hoy or pd.Timestamp.now()).normalize()
    filas = []
    for f in FUENTES:
        try:
            ud = f.leer()
            ud = None if pd.isna(ud) else pd.Timestamp(ud).normalize()
            err = ""
        except Exception as e:                                            # noqa: BLE001
            ud, err = None, f"no se pudo leer el último dato: {type(e).__name__}: {e}"
        if f.paso:
            reg = estado["pasos"].get(f.paso, {}); ult = reg.get("ultimo", {})
            ultima_corrida, resultado = ult.get("inicio"), ult.get("resultado") or "omitido"
            det_paso = ult.get("detalle") or "nunca corrió desde el orquestador"
            ex = _fecha(reg.get("ultima_exitosa"))
            frec = POR_NOMBRE[f.paso].frecuencia
        else:                                                             # contexto_diario: lo escribe el orquestador
            o = estado.get("orquestador", {}).get("diario", {})
            ultima_corrida, resultado = o.get("inicio"), o.get("resultado") or "omitido"
            det_paso = o.get("detalle") or "todavía no se ha escrito"
            ex = _fecha(o.get("inicio")) if resultado in ("ok", "sin_cambios") else None
            frec = DIARIA
        atraso = (hoy - ud).days if ud is not None else None
        motivos_rojo, motivos_amarillo = [], []
        if resultado == "fallo":
            motivos_rojo.append("la última corrida falló")
        if ud is None:
            motivos_rojo.append(err or "sin dato")
        elif f.tolerado is not None and atraso > f.tolerado:
            motivos_rojo.append(f"atraso {atraso} d > tolerado {f.tolerado} d")
        elif f.aviso is not None and atraso > f.aviso:
            motivos_amarillo.append(f"atraso {atraso} d > aviso {f.aviso} d")
        if resultado == "omitido":
            motivos_amarillo.append("omitido")
        limite_corrida = 2 * frec + 2
        if ex is None or (hoy - ex).days > limite_corrida:
            motivos_amarillo.append(f"sin corrida exitosa en {limite_corrida} d" if ex is not None else
                                    "sin corrida exitosa registrada")
        nivel = "rojo" if motivos_rojo else "amarillo" if motivos_amarillo else "verde"
        detalle = "; ".join(motivos_rojo + motivos_amarillo + [f"último resultado: {det_paso}", f.nota])
        filas.append(dict(fuente=f.fuente, archivo=f.archivo, ultimo_dato=ud.date().isoformat() if ud is not None else "",
                          ultima_corrida=ultima_corrida or "", resultado=resultado, dias_atraso=atraso,
                          atraso_tolerado=f.tolerado, nivel=nivel, usa_m3s=f.usa_m3s, detalle=detalle))
    pc = por_confirmar(hoy)
    filas.append(dict(
        fuente="por_confirmar", archivo="salidas/contexto/por_confirmar_*.csv",
        ultimo_dato=pc["proximo"].date().isoformat() if pc["proximo"] is not None else "",
        ultima_corrida=pc["actualizado"].isoformat(timespec="seconds") if pc["actualizado"] else "",
        resultado="fallo" if pc["errores"] else "ok",
        dias_atraso=(hoy - pc["proximo"]).days if pc["proximo"] is not None else None, atraso_tolerado=None,
        nivel="rojo" if pc["errores"] else "amarillo" if pc["n"] else "verde", usa_m3s=True,
        detalle=(f"{pc['n']} pendientes en los próximos {VENTANA_POR_CONFIRMAR} días: " + "; ".join(pc["items"])
                 if pc["n"] else f"sin pendientes en los próximos {VENTANA_POR_CONFIRMAR} días")
                + ("; " + "; ".join(pc["errores"]) if pc["errores"] else "")))
    F = pd.DataFrame(filas, columns=COLUMNAS_FRESCURA)
    F["dias_atraso"] = F.dias_atraso.astype("Int64"); F["atraso_tolerado"] = F.atraso_tolerado.astype("Int64")
    return F


def escribir_csv(tabla: pd.DataFrame, ruta: Path, **kw) -> None:
    """Escritura atómica: temporal y renombrado (si Power BI o Excel tienen el archivo abierto, falla aquí)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tabla.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n", **kw)
    os.replace(tmp, ruta)


def imprimir_frescura(F: pd.DataFrame, avisar=print) -> None:
    avisar(f"\n{'fuente':<17}{'último dato':<13}{'atraso':>7}{'tolera':>7}  {'nivel':<9}{'resultado':<12}M3s")
    for _, r in F.iterrows():
        a = "" if pd.isna(r.dias_atraso) else int(r.dias_atraso)
        t = "" if pd.isna(r.atraso_tolerado) else int(r.atraso_tolerado)
        avisar(f"{r.fuente:<17}{r.ultimo_dato:<13}{a!s:>7}{t!s:>7}  {r.nivel:<9}{r.resultado:<12}{'sí' if r.usa_m3s else 'no'}")
    malos = F[F.nivel.ne("verde")]
    for _, r in malos.iterrows():
        avisar(f"  [{r.nivel}] {r.fuente}: {r.detalle[:400]}")


# ====================================================================== orquestar
def orquestar(todo=False, solo=None, sin_hospital=False, avisar=print) -> int:
    hoy = pd.Timestamp.now()
    log = _log_del_dia(hoy)
    estado = cargar_estado()
    t0 = time.time()
    modo = "todo" if todo else f"solo {' '.join(solo)}" if solo else "lo que toca"
    estado["orquestador"].update(inicio=datetime.now().isoformat(timespec="seconds"), fin=None, codigo=None,
                                 modo=modo + (" sin hospital" if sin_hospital else ""))
    guardar_estado(estado)
    _escribir_log(log, f"\n######## {datetime.now():%Y-%m-%d %H:%M:%S} python -m contexto ({estado['orquestador']['modo']})\n")
    corridos, fallos_m3s = {}, []
    for paso in PASOS:
        if solo and paso.nombre not in solo:
            continue
        if paso.nombre == "hospital" and sin_hospital:
            avisar(f"{paso.nombre:<17} omitido (--sin-hospital)"); continue
        if not (todo or solo):
            si, por = toca(paso, estado, hoy)
            if not si:
                avisar(f"{paso.nombre:<17} no toca: {por}"); continue
        malos = [d for d in paso.depende if corridos.get(d) in ("fallo", "omitido_dep")]
        if malos:
            r = dict(inicio=datetime.now().isoformat(timespec="seconds"), resultado="omitido", codigo=None,
                     duracion_s=0.0, detalle=f"no se corre porque falló {', '.join(malos)}")
            corridos[paso.nombre] = "omitido_dep"
            _escribir_log(log, f"\n==== {r['inicio']} {paso.nombre}: {r['detalle']}\n")
        else:
            r = correr_paso(paso, log)
            corridos[paso.nombre] = r["resultado"]
        registrar(estado, paso.nombre, r); guardar_estado(estado)
        avisar(f"{paso.nombre:<17} {r['resultado']:<12}{r['duracion_s']:>7.1f} s  {r['detalle'][:110]}")
        if r["resultado"] == "fallo" and paso.usa_m3s:
            fallos_m3s.append(paso.nombre)

    # el contexto diario, en un subproceso (importa el modelo entero) y con tiempo límite
    td = time.time(); inicio = datetime.now().isoformat(timespec="seconds")
    _escribir_log(log, f"\n==== {inicio} contexto_diario ====\n")
    antes = hashlib.sha256(_contenido(DIARIO)).hexdigest() if DIARIO.exists() else None
    codigo, texto = correr_comando(["-m", "contexto.diario"], log, 1200)
    igual = codigo == 0 and DIARIO.exists() and hashlib.sha256(_contenido(DIARIO)).hexdigest() == antes
    rd = dict(inicio=inicio, resultado=("sin_cambios" if igual else "ok") if codigo == 0 else "fallo",
              duracion_s=round(time.time() - td, 1),
              detalle=_ultima_linea(texto) if codigo == 0 else
              (f"código {codigo}: {_ultima_linea(texto)}" if codigo is not None else "superó el tiempo límite"))
    estado["orquestador"]["diario"] = rd
    avisar(f"{'contexto_diario':<17} {rd['resultado']:<12}{rd['duracion_s']:>7.1f} s  {rd['detalle'][:110]}")
    if rd["resultado"] == "fallo":
        fallos_m3s.append("contexto_diario")

    F = frescura(estado, hoy)
    try:
        escribir_csv(F, FRESCURA)
    except OSError as e:
        avisar(f"no se pudo escribir {FRESCURA}: {e}"); fallos_m3s.append("frescura.csv")
    imprimir_frescura(F, avisar)
    codigo_salida = 1 if fallos_m3s else 0
    dur = round(time.time() - t0, 1)
    estado["orquestador"].update(fin=datetime.now().isoformat(timespec="seconds"), codigo=codigo_salida, duracion_s=dur,
                                 fallos_m3s=fallos_m3s)
    guardar_estado(estado)
    resumen = (f"\nTerminado en {dur} s. " + (f"Fallaron pasos que usa M3s: {', '.join(fallos_m3s)} (código 1)."
                                              if fallos_m3s else "Ningún paso que usa M3s falló (código 0)."))
    avisar(resumen)
    _escribir_log(log, resumen + "\n")
    F_txt = F[["fuente", "ultimo_dato", "dias_atraso", "atraso_tolerado", "nivel", "resultado"]].to_string(index=False)
    _escribir_log(log, F_txt + "\n")
    return codigo_salida
