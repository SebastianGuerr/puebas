"""
    python -m contexto                  corre los pasos que tocan según su frecuencia y la última corrida exitosa
    python -m contexto --todo           fuerza todos los pasos
    python -m contexto --solo hospital  corre solo esos pasos (uno o varios)
    python -m contexto --sin-hospital   omite la extracción de SQL Server
    python -m contexto --estado         solo imprime la frescura (no corre ni escribe nada)
    python -m contexto --esperar 90     espera a que termine la corrida de hoy (la usa operacion_semanal.cmd)
    python -m contexto --pasos          lista los pasos con su frecuencia

Código de salida: 0 bien; 1 si falló un paso que usa M3s (o el contexto diario); 3 si ya hay otra corrida en curso
o si --esperar agotó el tiempo. Detalle en contexto/docs/CONTEXTO_EXTERNO.md.
"""
import argparse
import sys

import contexto as cx


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m contexto")
    ap.add_argument("--todo", action="store_true", help="fuerza todos los pasos")
    ap.add_argument("--solo", nargs="+", choices=list(cx.POR_NOMBRE), metavar="PASO", help="corre solo esos pasos")
    ap.add_argument("--sin-hospital", action="store_true", help="omite la extracción de SQL Server")
    ap.add_argument("--estado", action="store_true", help="solo imprime la frescura")
    ap.add_argument("--esperar", type=float, metavar="MIN", help="espera a que termine la corrida de hoy")
    ap.add_argument("--pasos", action="store_true", help="lista los pasos")
    a = ap.parse_args(argv)
    try:                                             # la consola de Windows no siempre es UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if a.pasos:
        for p in cx.PASOS:
            print(f"{p.nombre:<17}{cx.NOMBRE_FRECUENCIA[p.frecuencia]:<9}{'M3s' if p.usa_m3s else '   '}  "
                  f"{' && '.join(' '.join(c) for c in p.comandos)}")
        return 0
    if a.estado:
        cx.imprimir_frescura(cx.frescura())
        return 0
    if a.esperar is not None:
        return cx.esperar(a.esperar)
    try:
        with cx.Bloqueo():
            return cx.orquestar(todo=a.todo, solo=a.solo, sin_hospital=a.sin_hospital)
    except cx.Ocupado as e:
        print(f"contexto: {e}; no se corre otra vez")
        return 3


if __name__ == "__main__":
    sys.exit(main())
