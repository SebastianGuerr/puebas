"""
El comando. Decide QUE figuras se hacen y EN QUE ORDEN; sin calculo dentro.

    python -m clustering.visualizaciones
    python -m clustering.visualizaciones --categoria categoria
    python -m clustering.visualizaciones --ventana

POR QUE LAS FIGURAS SON ARCHIVOS Y LAS TABLAS NO
    La decision de esta sesion es que las salidas van a la base y no a archivos
    sueltos. Un PNG no es una salida de datos: no se consulta y no se cruza.
    Meterlo como blob en DuckDB seria guardar medio megabyte binario al lado de
    los conteos para no poder hacer nada con el.

    Y las tablas que hay detras de estas figuras tampoco se guardan, por un
    motivo distinto: se recalculan en menos de un segundo desde el parquet.
    Guardarlas seria una copia que se puede quedar vieja sin que nadie lo note,
    que es justo el fallo del que venimos.
"""

import argparse
import sys


def _argumentos(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m clustering.visualizaciones",
        description="Dibuja el triage en el tiempo: hora, dia, semana y mes.")
    parser.add_argument("--categoria", nargs="?", const="categoria", default=None,
                        metavar="COLUMNA",
                        help="columna de nota_triage con la categoria. Sin este "
                             "argumento se dibuja la serie total desde 2020")
    parser.add_argument("--ventana", action="store_true",
                        help="ademas de guardar, abre las figuras en pantalla")
    parser.add_argument("--frecuencia", default="W", metavar="FREQ",
                        help="agregacion de la composicion (W semanal, ME mensual)")
    return parser.parse_args(argv)


def main(argv=None):
    args = _argumentos(argv)

    import matplotlib
    if not args.ventana:
        matplotlib.use("Agg")

    from matplotlib import pyplot as plt

    from clustering.visualizaciones import datos, figuras, rutas

    if args.categoria:
        try:
            tabla = datos.por_categoria(args.categoria)
        except RuntimeError as error:
            print(f"\n{error}\n")
            return 1
        etiqueta, sufijo = f"categoria '{args.categoria}'", args.categoria
    else:
        tabla = datos.total()
        etiqueta, sufijo = "serie total", "total"

    dias = tabla["dia"].nunique()
    print(f"\nFuente: {etiqueta}")
    print(f"  casillas dia x hora  {len(tabla):,}")
    print(f"  dias                 {dias:,}   "
          f"({tabla['dia'].min():%Y-%m-%d} a {tabla['dia'].max():%Y-%m-%d})")
    print(f"  triages              {tabla['n'].sum():,}")
    print(f"  categorias           {tabla['categoria'].nunique()}")

    destino = rutas.figuras()
    hechas, saltadas = [], []

    def _hacer(nombre, funcion):
        try:
            figura = funcion()
        except ValueError as error:
            saltadas.append((nombre, str(error)))
            return
        ruta = destino / f"{nombre}_{sufijo}.png"
        figura.savefig(ruta, dpi=130, bbox_inches="tight")
        hechas.append(ruta)
        if not args.ventana:
            plt.close(figura)

    serie = datos.serie_diaria(tabla)

    _hacer("01_reloj_semanal", lambda: figuras.reloj_semanal(tabla))
    _hacer("02_calendario", lambda: figuras.calendario(
        serie, titulo=f"Triages por dia -- {etiqueta}", etiqueta="triages/dia"))
    _hacer("03_calendario_dominante",
           lambda: figuras.calendario_dominante(tabla))
    _hacer("04_composicion",
           lambda: figuras.composicion(tabla, frecuencia=args.frecuencia))
    _hacer("05_polar", lambda: figuras.polar(tabla))
    _hacer("06_perfiles_hora", lambda: figuras.perfiles(tabla, eje="hora"))
    _hacer("07_perfiles_semana", lambda: figuras.perfiles(tabla, eje="dow"))
    _hacer("08_mes_anio", lambda: figuras.mes_anio(serie))

    print(f"\nFiguras en {destino.relative_to(rutas.RAIZ)}:")
    for ruta in hechas:
        print(f"  {ruta.name}")
    if saltadas:
        print("\nSaltadas -- cada una dice por que, y el motivo es un dato:")
        for nombre, razon in saltadas:
            print(f"  {nombre}: {razon}")

    if args.ventana:
        plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
