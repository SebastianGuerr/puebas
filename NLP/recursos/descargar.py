"""
Descargador de recursos externos a partir de un manifiesto versionado.
Aplica la politica de seguridad de PLAN.md S6 (dominio, https, zip slip,
extensiones ejecutables, verificacion de sha256). Ver docs/OPERACION.md para
el procedimiento y bitacora/2026-09-16-E3.1.md para las decisiones de diseno.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from NLP import rutas

RECURSOS_EXTERNOS = rutas.PAQUETE / "recursos_externos"
MANIFIESTO = rutas.DATOS / "recursos_manifiesto.json"

# Dominios de fuente oficial segun PLAN.md S6.1. El valor None significa "todo
# el dominio autorizado"; una lista de prefijos restringe a las rutas de las
# organizaciones autoras citadas en la politica (evita que un recurso de un
# tercero se cuele por compartir dominio con github.com).
_ORGS_GITHUB = ("/PlanTL-GOB-ES/", "/BSC-NLP4BIA/", "/ICB-UMA/", "/lcampillos/", "/hpi-dhc/")
ALLOWED_DOMINIOS: dict[str, tuple[str, ...] | None] = {
    "zenodo.org": None,
    "github.com": _ORGS_GITHUB,
    "raw.githubusercontent.com": _ORGS_GITHUB,
    "codeload.github.com": _ORGS_GITHUB,
    "datos.gov.co": None,
    "www.datos.gov.co": None,
    "geoportal.dane.gov.co": None,
    "www.dane.gov.co": None,
    "listadomedicamentos.aemps.gob.es": None,
    "cima.aemps.es": None,
    "www.ine.es": None,
    "ine.es": None,
    "pypi.org": None,
    "files.pythonhosted.org": None,
    "huggingface.co": None,
}

EXTENSIONES_EJECUTABLES = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".vbs", ".vbe", ".js",
    ".jse", ".jar", ".sh", ".scr", ".dll", ".apk", ".app", ".AppImage",
    ".gadget", ".wsf", ".msc", ".cpl",
}

TAMANO_BLOQUE = 256 * 1024


def cargar_manifiesto() -> list[dict]:
    """Lee el manifiesto versionado; documentacion del formato en PLAN.md S4.5."""
    with open(MANIFIESTO, "r", encoding="utf-8") as f:
        return json.load(f)


def url_permitida(url: str) -> tuple[bool, str]:
    """Valida esquema https y dominio/ruta contra ALLOWED_DOMINIOS."""
    p = urlparse(url)
    if p.scheme != "https":
        return False, f"esquema no https: {p.scheme!r}"
    dominio = p.hostname or ""
    if dominio not in ALLOWED_DOMINIOS:
        return False, f"dominio fuera de la politica de PLAN.md S6.1: {dominio}"
    prefijos = ALLOWED_DOMINIOS[dominio]
    if prefijos and not any(p.path.startswith(pref) for pref in prefijos):
        return False, f"ruta no autorizada para {dominio}: {p.path}"
    return True, ""


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(TAMANO_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar_archivo(url: str, destino: Path, user_agent: str | None) -> None:
    """Descarga en streaming a un archivo parcial y lo renombra al terminar."""
    cabeceras = {"User-Agent": user_agent} if user_agent else {}
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    peticion = Request(url, headers=cabeceras)
    with urlopen(peticion, timeout=180) as resp, open(parcial, "wb") as f:
        while True:
            bloque = resp.read(TAMANO_BLOQUE)
            if not bloque:
                break
            f.write(bloque)
    parcial.replace(destino)


def _ruta_segura(nombre_zip: str, directorio_destino: Path) -> bool:
    """Rechaza zip slip: rutas absolutas, con '..' o que salgan del destino."""
    if nombre_zip.startswith(("/", "\\")):
        return False
    ruta = Path(nombre_zip)
    if ruta.drive or ".." in ruta.parts:
        return False
    destino = (directorio_destino / nombre_zip).resolve()
    try:
        destino.relative_to(directorio_destino.resolve())
    except ValueError:
        return False
    return True


def extraer_seleccion(ruta_zip: Path, archivos_extraer: list[str], directorio_destino: Path) -> list[str]:
    """Lista el ZIP completo, y extrae solo lo pedido tras pasar los filtros de seguridad."""
    extraidos = []
    with zipfile.ZipFile(ruta_zip) as z:
        nombres = z.namelist()
        print(f"  contenido del ZIP ({len(nombres)} entradas):")
        for n in nombres:
            print(f"    {n}")
        for nombre in archivos_extraer:
            if nombre not in nombres:
                print(f"  [omitido] '{nombre}' no esta en el ZIP")
                continue
            if Path(nombre).suffix.lower() in EXTENSIONES_EJECUTABLES:
                print(f"  [rechazado] extension ejecutable: {nombre}")
                continue
            if not _ruta_segura(nombre, directorio_destino):
                print(f"  [rechazado] ruta fuera del directorio destino (zip slip): {nombre}")
                continue
            z.extract(nombre, directorio_destino)
            extraidos.append(nombre)
            print(f"  extraido: {nombre}")
    return extraidos


def procesar_recurso(entrada: dict, modo_verificar: bool) -> int:
    """Descarga o verifica un recurso. Retorna 0 si esta bien, 1 si se rechaza algo."""
    nombre = entrada["nombre"]

    if entrada.get("estado") == "rechazado":
        print(f"[{nombre}] estado=rechazado en el manifiesto: {entrada.get('motivo_rechazo')}")
        return 0

    ok, motivo = url_permitida(entrada["url"])
    if not ok:
        print(f"[{nombre}] RECHAZADO por politica de seguridad: {motivo}")
        return 1

    directorio = RECURSOS_EXTERNOS / nombre
    nombre_archivo = Path(urlparse(entrada["url"]).path).name or nombre
    destino = directorio / nombre_archivo

    if modo_verificar:
        if not destino.exists():
            print(f"[{nombre}] no hay archivo descargado en {destino}; nada que verificar")
            return 0
    else:
        print(f"[{nombre}] descargando {entrada['url']} -> {destino}")
        descargar_archivo(entrada["url"], destino, entrada.get("user_agent"))

    digest = sha256_de(destino)
    tamano = destino.stat().st_size
    print(f"[{nombre}] sha256={digest} tamano_bytes={tamano}")

    esperado = entrada.get("sha256")
    if esperado:
        if digest != esperado:
            destino.unlink()
            print(
                f"[{nombre}] RECHAZADO: sha256 no coincide con el manifiesto "
                f"(esperado {esperado}, obtenido {digest}). Archivo borrado."
            )
            return 1
        print(f"[{nombre}] sha256 verificado contra el manifiesto.")
    else:
        print(
            f"[{nombre}] el manifiesto no trae sha256 de referencia: el archivo se "
            "conserva pero una persona debe revisarlo y fijar el hash a mano "
            "(ver bitacora/2026-09-16-E3.1.md, seccion de decision)."
        )

    if not modo_verificar and destino.suffix.lower() == ".zip" and entrada.get("archivos_extraer"):
        extraer_seleccion(destino, entrada["archivos_extraer"], directorio)

    return 0


def seleccionar(manifiesto: list[dict], solo: str | None, modo_verificar: bool) -> list[dict]:
    if solo:
        entradas = [e for e in manifiesto if e["nombre"] == solo]
        if not entradas:
            raise SystemExit(f"no existe '{solo}' en {MANIFIESTO}")
        return entradas
    if modo_verificar:
        return [e for e in manifiesto if e.get("estado") in ("descargado", "verificado")]
    return [e for e in manifiesto if e.get("estado") == "pendiente"]


def listar(manifiesto: list[dict]) -> None:
    for e in manifiesto:
        licencia = e.get("licencia") or "(sin licencia identificada)"
        print(f"{e['nombre']:32s} {e['estado']:11s} {licencia:22s} {e['url']}")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(
        description="Descarga y verifica recursos externos segun datos/recursos_manifiesto.json (E3.1)."
    )
    parser.add_argument("--listar", action="store_true", help="imprime el manifiesto y termina")
    parser.add_argument("--solo", metavar="NOMBRE", help="limita la accion a un recurso")
    parser.add_argument(
        "--verificar", action="store_true",
        help="recalcula el sha256 de lo ya descargado en vez de descargar de nuevo",
    )
    args = parser.parse_args(argv)

    manifiesto = cargar_manifiesto()

    if args.listar:
        listar(manifiesto)
        return 0

    entradas = seleccionar(manifiesto, args.solo, args.verificar)
    if not entradas:
        print("nada que hacer: ningun recurso en el estado esperado")
        return 0

    codigo = 0
    for entrada in entradas:
        resultado = procesar_recurso(entrada, args.verificar)
        codigo = resultado or codigo
    return codigo


if __name__ == "__main__":
    sys.exit(main())
