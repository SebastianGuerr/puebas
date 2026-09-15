"""
El analisis principal: diseno cruzado por estratos de tiempo. Lo que SI concluye.

    python -m patrones --modelar     ajusta y escribe modelos.csv

LA DIFERENCIA CON asociacion.py, QUE ES TODA LA DIFERENCIA
    asociacion.py mide si dos series se mueven juntas. Este modulo estima
    CUANTO cambia el riesgo, ajustando por lo que hay que ajustar, y devuelve un
    numero con unidades e intervalo de confianza. Es lo unico de este paquete
    que se puede reportar como resultado.

    Que uno sea exploratorio y el otro confirmatorio no es una jerarquia de
    calidad del codigo: es que responden preguntas distintas y solo la segunda
    admite una respuesta.

POR QUE ESTE DISENO Y NO UNA REGRESION DE SERIE TEMPORAL
    Es LA decision de este modulo y esta forzada por el tamano de la ventana.

    Una regresion de serie temporal ajusta la estacionalidad con una funcion
    del tiempo -- splines o armonicos -- y para eso hay que ESTIMARLA. Con 615
    dias hay 1,7 ciclos anuales: cada mes del ano se ha visto una vez o dos. Una
    curva estacional ajustada sobre eso no esta estimada, esta inventada, y todo
    lo que la variable climatica comparta con ella se reparte al azar entre las
    dos.

    El diseno cruzado por estratos no estima la estacionalidad: la ELIMINA. Los
    estratos son (ano, mes, dia de la semana), y dentro de un estrato solo caen
    los cuatro o cinco lunes del mismo mes del mismo ano. La comparacion es
    entre esos lunes.

    Las consecuencias, que son exactamente lo que hace falta aqui:

        la tendencia de largo plazo         no entra: no varia dentro del mes
        la estacionalidad anual             no entra: por lo mismo
        el ciclo semanal                    no entra: todos son el mismo dia
        la deriva de la cobertura del motivo no entra: es tendencia

    Los cuatro problemas que documenta clustering/fechas.py desaparecen por
    construccion en vez de por ajuste. A cambio, la pregunta que se puede
    responder es mas estrecha, y conviene decirlo claro: 'entre dos lunes de
    marzo de 2026, ¿consulto mas gente por este motivo en el que llovio mas?'.
    Es una pregunta de CORTO PLAZO. El efecto de la temporada de lluvias sobre
    el ano no se puede responder con estos datos, con este diseno ni con otro.

EL DESPLAZAMIENTO NO ES OPCIONAL
    El desenlace es el conteo de notas del tema ese dia, y va con
    log(procesadas) como desplazamiento.

    Sin el, el modelo confunde 'mas gente consulto por este motivo' con 'mas
    gente consulto'. Un festivo baja el total un 17% y sin desplazamiento eso
    aparece como una caida de TODOS los temas a la vez, en todos los modelos,
    lo que ademas rompe la independencia entre pruebas.

    Con el, lo que se estima es un cambio en la COMPOSICION: que fraccion de
    los que llegaron venia por este motivo. Es lo que mide un sistema de
    vigilancia sindromica y es lo que la serie puede sostener.

SOLO SE PRUEBA LO QUE ESTA ESCRITO EN datos/variables.csv
    Ese archivo se edita a mano y dice, con el motivo al lado, que exposiciones
    son PRIMARIAS. Las primarias se corrigen entre ellas; el resto sale
    marcado como exploratorio y no se mezcla en la misma correccion.

    Es la unica forma de que 'preespecificado' signifique algo. Un analisis en
    el que la lista de hipotesis se decide despues de ver las correlaciones no
    es confirmatorio aunque use el mismo modelo, y como aqui el paso anterior
    ES una busqueda de correlaciones, la tentacion esta servida.

    Regla practica: si una fila de variables.csv se agrega DESPUES de mirar
    asociacion.csv, va con primaria=no. Siempre.
"""

import numpy as np
import pandas as pd

from patrones import rutas

FDR = 0.05

# Dias minimos con conteo no nulo para intentar ajustar un tema. Por debajo el
# ajuste condicional no converge o converge a cualquier cosa: la mayoria de los
# estratos aporta cero y la verosimilitud se queda sin informacion.
MINIMO_DIAS_CON_CASO = 60


def preregistro(ruta=None):
    """
    Las hipotesis escritas. Sube un error claro si no estan.

    No hay valor por defecto a proposito: que el archivo tenga que existir es
    lo que obliga a escribir las hipotesis antes de correr el analisis.
    """
    ruta = ruta or rutas.VARIABLES
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}.\n"
            f"Es la lista de hipotesis preespecificadas y sin ella este modulo "
            f"no tiene nada que probar.\n"
            f"Columnas: variable, ventana_dias, familia, primaria, motivo.")
    tabla = pd.read_csv(ruta, encoding="utf-8-sig")
    faltan = {"variable", "ventana_dias", "primaria"} - set(tabla.columns)
    if faltan:
        raise SystemExit(f"A {ruta} le faltan columnas: {sorted(faltan)}")
    tabla["primaria"] = (tabla["primaria"].astype(str).str.strip().str.lower()
                         .isin(["si", "sí", "true", "1"]))
    return tabla


def estratos(fechas):
    """
    (ano, mes, dia de la semana). La unidad de comparacion del diseno.

    Un estrato agrupa los lunes de marzo de 2026, o los sabados de julio de
    2025. Todo lo que sea constante dentro de un estrato -- la tendencia, la
    estacion del ano, el efecto del dia de la semana -- sale de la estimacion
    sin que haya que modelarlo.
    """
    fechas = pd.to_datetime(pd.Series(fechas))
    return (fechas.dt.year.astype(str) + "-"
            + fechas.dt.month.astype(str).str.zfill(2) + "-"
            + fechas.dt.dayofweek.astype(str))


def _exposicion(diario, variable, ventana):
    """La exposicion promediada sobre su ventana, estandarizada."""
    serie = diario[variable].astype(float)
    if ventana > 1:
        serie = serie.rolling(ventana, min_periods=max(2, ventana // 2)).mean()
    valores = serie.to_numpy(dtype=float)
    desviacion = np.nanstd(valores, ddof=1)
    if not np.isfinite(desviacion) or desviacion == 0:
        return None, np.nan
    # Estandarizada para que el coeficiente sea 'por 1 SD' y los riesgos
    # relativos de variables con unidades distintas -- milimetros, grados,
    # banderas -- se puedan poner en la misma tabla y comparar.
    return (valores - np.nanmean(valores)) / desviacion, float(desviacion)


def ajustar(conteos, expuestos, exposicion, estrato):
    """
    Un modelo. Devuelve el riesgo relativo por 1 SD de exposicion.

    Poisson condicional y no logistico condicional: no hace falta expandir los
    datos a un caso por fila y, a diferencia del logistico, admite despues un
    ajuste por sobredispersion.
    """
    from statsmodels.discrete.conditional_models import ConditionalPoisson

    datos = pd.DataFrame({"y": conteos, "n": expuestos, "x": exposicion,
                          "g": estrato}).dropna()
    datos = datos[datos["n"] > 0]

    if len(datos) < MINIMO_DIAS_CON_CASO or datos["y"].sum() < 1:
        return None
    if datos["x"].std() == 0:
        return None
    # Un estrato con una sola fila no aporta nada a la verosimilitud
    # condicional y ademas confunde el recuento de lo que se uso.
    tamanos = datos.groupby("g")["y"].transform("size")
    datos = datos[tamanos > 1]
    if len(datos) < MINIMO_DIAS_CON_CASO:
        return None

    try:
        modelo = ConditionalPoisson(
            datos["y"].to_numpy(dtype=float),
            datos[["x"]].to_numpy(dtype=float),
            groups=datos["g"].to_numpy(),
            offset=np.log(datos["n"].to_numpy(dtype=float))).fit()
    except Exception:
        # El ajuste condicional no converge con relativa frecuencia en series
        # escasas. Es un resultado -- 'no se pudo estimar' -- y se devuelve
        # como tal en vez de interrumpir la corrida entera.
        return None

    beta = float(modelo.params[0])
    error = float(modelo.bse[0])
    return {
        "rr": float(np.exp(beta)),
        "rr_bajo": float(np.exp(beta - 1.96 * error)),
        "rr_alto": float(np.exp(beta + 1.96 * error)),
        "p": float(modelo.pvalues[0]),
        "dias": int(len(datos)),
        "estratos": int(datos["g"].nunique()),
        "eventos": int(datos["y"].sum()),
    }


def correr(serie, diario, temas, hipotesis=None, fdr=FDR, aviso=print):
    """
    Una fila por (tema, hipotesis). La tabla de resultados del paquete.

    La correccion por multiplicidad se aplica DENTRO de las primarias y aparte
    dentro de las exploratorias. Mezclarlas le quitaria potencia a las
    primarias por culpa de pruebas que nunca fueron la pregunta.
    """
    hipotesis = preregistro() if hipotesis is None else hipotesis
    diario = diario.sort_values("fecha").reset_index(drop=True)
    estrato = estratos(diario["fecha"]).to_numpy()

    disponibles = set(diario.columns)
    ausentes = sorted(set(hipotesis["variable"]) - disponibles)
    if ausentes:
        aviso(f"  aviso: {ausentes} estan en variables.csv pero no en el "
              f"calendario. Se saltan.")
        hipotesis = hipotesis[~hipotesis["variable"].isin(ausentes)]

    filas = []
    for ancla, nombre in temas:
        parcial = (serie[serie["ancla"] == ancla]
                   .sort_values("fecha")[["fecha", "notas", "procesadas"]])
        alineada = diario[["fecha"]].merge(parcial, on="fecha", how="left")
        y = alineada["notas"].to_numpy(dtype=float)
        n = alineada["procesadas"].to_numpy(dtype=float)

        for _, hipo in hipotesis.iterrows():
            x, desviacion = _exposicion(diario, hipo["variable"],
                                        int(hipo["ventana_dias"]))
            resultado = ajustar(y, n, x, estrato) if x is not None else None
            fila = {
                "ancla": ancla, "nombre": nombre,
                "variable": hipo["variable"],
                "ventana_dias": int(hipo["ventana_dias"]),
                "primaria": bool(hipo["primaria"]),
                "sd_variable": desviacion,
            }
            fila.update(resultado or {"rr": np.nan, "rr_bajo": np.nan,
                                      "rr_alto": np.nan, "p": np.nan,
                                      "dias": 0, "estratos": 0, "eventos": 0})
            filas.append(fila)

    tabla = pd.DataFrame(filas)
    ajustados = int(tabla["p"].notna().sum())
    aviso(f"  {ajustados} modelos ajustados de {len(tabla)} intentados")

    tabla["p_corregido"] = np.nan
    tabla["sobrevive"] = False
    from statsmodels.stats.multitest import multipletests
    for primaria in (True, False):
        seleccion = (tabla["primaria"] == primaria) & tabla["p"].notna()
        if not seleccion.any():
            continue
        pasa, corregidos, *_ = multipletests(tabla.loc[seleccion, "p"],
                                             alpha=fdr, method="fdr_bh")
        tabla.loc[seleccion, "p_corregido"] = corregidos
        tabla.loc[seleccion, "sobrevive"] = pasa

    return tabla.sort_values(["primaria", "p_corregido"],
                             ascending=[False, True],
                             na_position="last").reset_index(drop=True)


def guardar(tabla):
    """Escribe la tabla de modelos y devuelve su ruta."""
    tabla.to_csv(rutas.MODELOS, index=False, encoding="utf-8-sig")
    return rutas.MODELOS


def informe(tabla, fdr=FDR):
    """El resultado, con lo que significa y lo que no."""
    primarias = tabla[tabla["primaria"] & tabla["p"].notna()]
    exploratorias = tabla[~tabla["primaria"] & tabla["p"].notna()]

    lineas = [
        "ANALISIS PRINCIPAL: DISENO CRUZADO POR ESTRATOS DE TIEMPO",
        "",
        "  Estratos: (ano, mes, dia de la semana). Cada dia se compara solo",
        "  contra los otros dias del mismo mes y el mismo dia de la semana, de",
        "  modo que la tendencia, la estacion y el ciclo semanal no entran.",
        "",
        "  Desenlace: notas del tema ese dia.",
        "  Desplazamiento: log(notas procesadas ese dia), asi que lo que se",
        "  estima es un cambio de COMPOSICION y no de volumen.",
        "  Efecto: riesgo relativo por 1 desviacion estandar de la exposicion.",
        "",
        f"  primarias (preespecificadas):  {len(primarias)} modelos",
        f"  exploratorias:                 {len(exploratorias)} modelos",
        f"  correccion Benjamini-Hochberg al {fdr:.0%}, por separado en cada grupo",
        "",
        "=" * 70,
        "PRIMARIAS",
        "",
        f"  {'tema':<24} {'variable':<22} {'RR':>6} {'IC 95%':>16} {'p corr':>8}",
    ]

    if primarias.empty:
        lineas.append("  (ningun modelo pudo ajustarse)")
    for _, fila in primarias.iterrows():
        marca = "*" if fila["sobrevive"] else " "
        lineas.append(
            f" {marca}{fila['nombre'][:24]:<24} {fila['variable'][:22]:<22} "
            f"{fila['rr']:>6.3f} "
            f"{fila['rr_bajo']:>7.3f}-{fila['rr_alto']:<7.3f} "
            f"{fila['p_corregido']:>8.4f}")

    vivos = int(tabla["sobrevive"].sum())
    lineas += ["", "=" * 70, "COMO SE LEE ESTO", ""]

    if vivos == 0:
        lineas += [
            "  Ningun efecto sobrevive a la correccion. Con la potencia que",
            "  tiene este corpus era el resultado esperado y NO significa que",
            "  el clima no influya: significa que estos datos no pueden",
            "  distinguirlo. Ver potencia.py.",
            "",
            "  Lo que si se puede afirmar es el intervalo: si el IC 95% de una",
            "  fila va de 0,95 a 1,08, lo que se ha descartado es un efecto",
            "  mayor al 8%, y nada mas. Mirar los intervalos y no los p.",
        ]
    else:
        lineas += [
            f"  {vivos} efecto(s) sobreviven. Antes de reportarlos:",
            "",
            "  1. Comprobar que el IC no sea absurdamente ancho. Un RR de 1,4",
            "     con IC de 1,02 a 1,92 es 'algo pasa', no 'sube un 40%'.",
            "  2. Mirar el perfil de rezagos en salidas/figuras/: un efecto",
            "     real tiene forma a lo largo de los dias, no un pico suelto.",
            "  3. Mirar el calendario doble de ese tema. Si el efecto es real",
            "     tiene que haber episodios concretos donde se vea.",
            "  4. Si la fila es exploratoria y no primaria, es una hipotesis",
            "     para la proxima ventana de datos, no un hallazgo.",
        ]

    lineas += [
        "",
        "LO QUE ESTE DISENO NO PUEDE RESPONDER, Y NO ES UN DEFECTO",
        "",
        "  La pregunta contestada es de corto plazo: entre dias parecidos del",
        "  mismo mes, ¿cambia la composicion de motivos con la exposicion?",
        "",
        "  '¿La temporada de lluvias trae mas consultas respiratorias?' es otra",
        "  pregunta, y con 1,7 ciclos anuales NO se puede responder con estos",
        "  datos. No hay diseno que lo arregle: se necesita mas historia.",
    ]
    return "\n".join(lineas) + "\n"
