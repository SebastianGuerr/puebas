"""
Las pruebas del lift y del camino por categoria, contra datos inventados.

POR QUE CONTRA DATOS INVENTADOS Y NO CONTRA EL CORPUS
    Porque el corpus todavia no tiene categorias -- van 1.390 notas de 93.991
    y ninguna clasificada -- y porque una prueba tiene que fallar cuando el
    calculo este mal, no cuando los datos cambien.

    Aqui se construye una tabla en la que la respuesta correcta se conoce de
    antemano: una categoria puesta a mano en unas horas concretas tiene que dar
    lift alto ahi y bajo en el resto. Si el lift estuviera al reves, o
    normalizado por el sitio equivocado, estas pruebas lo dicen.

    python -m clustering.visualizaciones.pruebas
"""

import numpy as np
import pandas as pd

from clustering.visualizaciones import datos, figuras


def _tabla_sintetica(semilla=42):
    """
    Dos categorias con un patron conocido sobre 120 dias.

    'diurna' se reparte igual a todas horas. 'nocturna' solo aparece entre las
    0 y las 5. El lift de 'nocturna' tiene que ser claramente mayor que 1 en
    esas horas y claramente menor en el resto.
    """
    azar = np.random.default_rng(semilla)
    dias = pd.date_range("2025-01-01", periods=120, freq="D")
    filas = []
    for dia in dias:
        for hora in range(24):
            filas.append((dia, hora, "diurna", int(azar.poisson(10))))
            nocturna = 12 if hora < 6 else 1
            filas.append((dia, hora, "nocturna", int(azar.poisson(nocturna))))
    return pd.DataFrame(filas, columns=["dia", "hora", "categoria", "n"])


def probar_lift_detecta_el_patron():
    marco = datos.marco(_tabla_sintetica())
    medido = datos.lift(marco, ["hora"])
    nocturna = medido[medido["categoria"] == "nocturna"].set_index("hora")["lift"]

    madrugada = nocturna.loc[0:5].mean()
    resto = nocturna.loc[6:23].mean()
    assert madrugada > 1.5, f"la madrugada deberia destacar, dio {madrugada:.2f}"
    assert resto < 0.8, f"el resto deberia hundirse, dio {resto:.2f}"
    assert madrugada > resto * 2, "el contraste es demasiado flojo"
    return f"lift nocturna: madrugada {madrugada:.2f} vs resto {resto:.2f}"


def probar_lift_es_uno_sin_patron():
    """
    La prueba que mas importa: si una categoria NO depende de la casilla, el
    lift tiene que dar 1,0. Un lift que se aleja de 1 sin que haya patron seria
    un hallazgo fabricado por el metodo.
    """
    azar = np.random.default_rng(7)
    dias = pd.date_range("2025-01-01", periods=200, freq="D")
    filas = [(dia, hora, clase, int(azar.poisson(20)))
             for dia in dias for hora in range(24) for clase in ("a", "b")]
    marco = datos.marco(pd.DataFrame(filas, columns=["dia", "hora", "categoria", "n"]))

    medido = datos.lift(marco, ["hora"])
    desvio = (medido["lift"] - 1.0).abs().max()
    assert desvio < 0.1, f"sin patron el lift deberia rondar 1,0; se fue a {1 + desvio:.3f}"
    return f"sin patron, desvio maximo del lift: {desvio:.4f}"


def probar_la_cobertura_se_cancela():
    """
    El lift no debe moverse si cae la fraccion de notas con motivo escrito,
    mientras esa caida no dependa de la categoria. Es el supuesto declarado en
    datos.py y aqui se comprueba que el calculo lo cumple.
    """
    marco = datos.marco(_tabla_sintetica())
    antes = datos.lift(marco, ["hora"]).set_index(["categoria", "hora"])["lift"]

    # La segunda mitad del periodo pierde el 40% de las notas, por igual en
    # las dos categorias. Es una caida de cobertura, no de composicion.
    recortado = marco.copy()
    tarde = recortado["dia"] > recortado["dia"].median()
    recortado.loc[tarde, "n"] = (recortado.loc[tarde, "n"] * 0.6).round().astype(int)
    despues = datos.lift(recortado, ["hora"]).set_index(["categoria", "hora"])["lift"]

    desvio = (antes - despues).abs().max()
    assert desvio < 0.05, f"la cobertura no se cancelo: el lift se movio {desvio:.3f}"
    return f"cobertura -40%: el lift se movio como mucho {desvio:.4f}"


def probar_tapa_las_casillas_flacas():
    azar = np.random.default_rng(1)
    dias = pd.date_range("2025-01-01", periods=10, freq="D")
    filas = [(dia, hora, clase, int(azar.poisson(0.2)))
             for dia in dias for hora in range(24) for clase in ("a", "b")]
    marco = datos.marco(pd.DataFrame(filas, columns=["dia", "hora", "categoria", "n"]))

    medido = datos.lift(marco, ["dow", "hora"])
    assert not medido["fiable"].any(), \
        "con conteos minusculos ninguna casilla deberia declararse fiable"
    return f"{len(medido)} casillas flacas, {int(medido['fiable'].sum())} declaradas fiables"


def probar_las_figuras_de_categoria_salen():
    """Las cuatro figuras que hoy se saltan por falta de categorias."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    tabla = _tabla_sintetica()
    hechas = []
    for nombre, funcion in [
        ("reloj_semanal", lambda: figuras.reloj_semanal(tabla, categoria="nocturna")),
        ("calendario_dominante", lambda: figuras.calendario_dominante(tabla)),
        ("composicion", lambda: figuras.composicion(tabla)),
        ("polar", lambda: figuras.polar(tabla)),
        ("perfiles_hora", lambda: figuras.perfiles(tabla, eje="hora")),
        ("perfiles_semana", lambda: figuras.perfiles(tabla, eje="dow")),
    ]:
        figura = funcion()
        assert figura.axes, f"{nombre} salio sin ejes"
        plt.close(figura)
        hechas.append(nombre)
    return f"{len(hechas)} figuras de categoria construidas: {', '.join(hechas)}"


def main():
    pruebas = [probar_lift_detecta_el_patron,
               probar_lift_es_uno_sin_patron,
               probar_la_cobertura_se_cancela,
               probar_tapa_las_casillas_flacas,
               probar_las_figuras_de_categoria_salen]
    fallos = 0
    for prueba in pruebas:
        try:
            detalle = prueba()
            print(f"  OK   {prueba.__name__}\n         {detalle}")
        except AssertionError as error:
            fallos += 1
            print(f"  FALLA {prueba.__name__}\n         {error}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
