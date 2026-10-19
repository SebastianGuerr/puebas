"""
La página del tablero de Power BI para los jefes de urgencias (prediccion.pbip), escrita como archivos PBIR.
Una página 1280x720, sin scroll, con el estilo del tablero de urgencias del hospital. Rehace
prediccion.Report/definition/pages/ desde cero: correr con Power BI Desktop CERRADO.

    python -m operacion.powerbi_pagina

Las medidas que usa (carpeta «Tablero» de la tabla Medidas) viven en prediccion.SemanticModel. Por qué es así:
docs/CONTEXTO.md, entradas «2026-10-19 (Power BI ...)»; uso y mantenimiento: operacion/docs/POWERBI.md.
"""
import json, shutil, sys, hashlib
from pathlib import Path

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PGS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"


def nombre(*p): return hashlib.md5("|".join(map(str, p)).encode()).hexdigest()[:20]
def lit(v):
    if isinstance(v, bool): return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)): return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}}
def M(p): return {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": p}}
def C(t, p): return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": p}}
def ref(f):
    k = "Measure" if "Measure" in f else "Column"
    return f"{f[k]['Expression']['SourceRef']['Entity']}.{f[k]['Property']}", f[k]["Property"]
def proy(f, alias=None):
    q, n = ref(f); d = {"field": f, "queryRef": q, "nativeQueryRef": n}
    if alias: d["displayName"] = alias
    return d
def color_medida(p): return {"solid": {"color": {"expr": M(p)}}}
def color(hexa): return {"solid": {"color": lit(hexa)}}
def titulo(texto, tam=11):
    if texto is None: return {"title": [{"properties": {"show": lit(False)}}]}
    return {"title": [{"properties": {"show": lit(True), "text": lit(texto), "fontSize": lit(tam)}}]}


class Pagina:
    def __init__(self, nombre_vis, alto, ancho=1280):
        self.id = nombre(nombre_vis); self.nombre = nombre_vis; self.alto = alto; self.ancho = ancho; self.vis = []; self.z = 0

    def poner(self, x, y, w, h, visual, cont=None):
        self.z += 1
        v = {"$schema": VC, "name": nombre(self.nombre, self.z), "position": {"x": x, "y": y, "z": self.z * 1000,
             "height": h, "width": w, "tabOrder": self.z * 1000}, "visual": visual}
        if cont: v["visual"]["visualContainerObjects"] = cont
        v["visual"]["drillFilterOtherVisuals"] = True
        self.vis.append(v)

    # ------------------------------------------------------------------ tipos de visual
    def texto(self, x, y, w, h, parrafos):
        """parrafos: lista de listas de (texto, estilo)."""
        ps = [{"textRuns": [{"value": t, "textStyle": e} for t, e in p]} for p in parrafos]
        self.poner(x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": ps}}]}})

    def tarjeta(self, x, y, w, h, medida, tit, tam=20, color_m=None, ajustar=False):
        labels = {"fontSize": lit(tam)}
        if color_m: labels["color"] = color_medida(color_m)
        obj = {"labels": [{"properties": labels}], "categoryLabels": [{"properties": {"show": lit(False)}}]}
        if ajustar: obj["wordWrap"] = [{"properties": {"show": lit(True)}}]
        self.poner(x, y, w, h, {"visualType": "card", "query": {"queryState": {"Values": {"projections": [proy(M(medida))]}}},
                                "objects": obj}, titulo(tit))

    def filtro(self, x, y, w, h, col, tit, desplegable=True):
        obj = {"data": [{"properties": {"mode": lit("Dropdown")}}]} if desplegable else {}
        obj["header"] = [{"properties": {"show": lit(True), "text": lit(tit)}}]
        self.poner(x, y, w, h, {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proy(col)]}}},
                                "objects": obj})

    def matriz(self, x, y, w, h, filas, columnas, valores, tit, fondo=None, letra=None, orden=None, alto_letra=10):
        q = {"queryState": {"Rows": {"projections": [proy(f) for f in filas]},
                            "Columns": {"projections": [proy(f) for f in columnas]},
                            "Values": {"projections": [proy(f) for f in valores]}}}
        if orden: q["sortDefinition"] = {"sort": [{"field": orden[0], "direction": orden[1]}], "isDefaultSort": False}
        obj = {"subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}],
               "values": [{"properties": {"fontSize": lit(alto_letra), "wordWrap": lit(True)}}],
               "columnHeaders": [{"properties": {"fontSize": lit(alto_letra), "alignment": lit("Center")}}],
               "rowHeaders": [{"properties": {"fontSize": lit(alto_letra)}}]}
        for f in valores:
            props = {}
            if fondo: props["backColor"] = color_medida(fondo)
            if letra: props["fontColor"] = color_medida(letra)
            if props:
                obj["values"].append({"properties": props, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                                                         "metadata": ref(f)[0]}})
        self.poner(x, y, w, h, {"visualType": "pivotTable", "query": q, "objects": obj}, titulo(tit))

    def tabla(self, x, y, w, h, campos, tit, fondo_de=None):
        obj = {"values": [{"properties": {"wordWrap": lit(True)}}]}
        if fondo_de:
            campo, medida = fondo_de
            obj["values"].append({"properties": {"backColor": color_medida(medida)},
                                  "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": ref(campo)[0]}})
        self.poner(x, y, w, h, {"visualType": "tableEx", "query": {"queryState": {"Values": {"projections": [proy(*c) if isinstance(c, tuple) else proy(c) for c in campos]}}},
                                "objects": obj}, titulo(tit))

    def grafico(self, tipo, x, y, w, h, categoria, ys, tit, serie=None, tooltips=(), colores=None, etiquetas=False):
        qs = {"Category": {"projections": [proy(categoria)]}, "Y": {"projections": [proy(*f) if isinstance(f, tuple) else proy(f) for f in ys]}}
        if serie: qs["Series"] = {"projections": [proy(serie)]}
        if tooltips: qs["Tooltips"] = {"projections": [proy(f) for f in tooltips]}
        obj = {}
        if colores:
            obj["dataPoint"] = [{"properties": {"fill": color(c)}, "selector": {"metadata": ref(f[0] if isinstance(f, tuple) else f)[0]}}
                                for f, c in zip(ys, colores)]
        if etiquetas: obj["labels"] = [{"properties": {"show": lit(True)}}]
        self.poner(x, y, w, h, {"visualType": tipo, "query": {"queryState": qs}, "objects": obj}, titulo(tit))

    def escribir(self, raiz):
        d = raiz / "definition" / "pages" / self.id
        (d / "visuals").mkdir(parents=True, exist_ok=True)
        (d / "page.json").write_text(json.dumps({"$schema": PG, "name": self.id, "displayName": self.nombre,
                                                 "displayOption": "FitToWidth", "height": self.alto, "width": self.ancho},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
        for v in self.vis:
            (d / "visuals" / v["name"]).mkdir(exist_ok=True)
            (d / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")


AZUL_SES, FONDO, BLANCO, BORDE = "#176DAA", "#F0F0F0", "#FFFFFF", "#DADCE0"
TINTA, TINTA2, MUTED = "#252423", "#52514e", "#898781"
BARRA = "#2a78d6"
ROJOS = ["#fde7e6", "#f8c4c2", "#f09491", "#e34948", "#a82a2a"]
G = 12


def caja(titulo_txt=None, titulo_medida=None, sub=None, fondo=True, borde=True, tam=10):
    o = {"background": [{"properties": {"show": lit(fondo), "color": color(BLANCO), "transparency": lit(0)}}],
         "border": [{"properties": {"show": lit(borde), "color": color(BORDE), "radius": lit(10)}}],
         "dropShadow": [{"properties": {"show": lit(False)}}], "visualHeader": [{"properties": {"show": lit(False)}}],
         "padding": [{"properties": {"top": lit(6), "bottom": lit(4), "left": lit(10), "right": lit(10)}}]}
    if titulo_txt or titulo_medida:
        o["title"] = [{"properties": {"show": lit(True), "fontSize": lit(tam), "fontColor": color(AZUL_SES), "bold": lit(True),
                                      "text": {"expr": M(titulo_medida)} if titulo_medida else lit(titulo_txt)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    o["subTitle"] = [{"properties": {"show": lit(bool(sub)), **({"text": lit(sub), "fontSize": lit(8), "fontColor": color(MUTED)} if sub else {})}}]
    return o


def tarjeta(p, x, y, w, h, medida, tam, tinta=TINTA, tinta_medida=None, titulo_medida=None, negrita=False, cont=None):
    labels = {"fontSize": lit(tam), "labelDisplayUnits": lit(1), "labelPrecision": lit(0),
              "color": color_medida(tinta_medida) if tinta_medida else color(tinta)}
    if negrita: labels["bold"] = lit(True)
    p.poner(x, y, w, h, {"visualType": "card", "query": {"queryState": {"Values": {"projections": [proy(M(medida))]}}},
                         "objects": {"labels": [{"properties": labels}], "categoryLabels": [{"properties": {"show": lit(False)}}],
                                     "wordWrap": [{"properties": {"show": lit(True)}}]}},
            cont or caja(titulo_medida=titulo_medida))


def pildora(p, x, y, w, h, medida, fondo_hex, tinta_hex):
    cont = caja(fondo=True, borde=False)
    cont["background"] = [{"properties": {"show": lit(True), "color": color(fondo_hex), "transparency": lit(0)}}]
    cont["border"] = [{"properties": {"show": lit(True), "color": color(fondo_hex), "radius": lit(14)}}]
    cont["padding"] = [{"properties": {"top": lit(0), "bottom": lit(0), "left": lit(4), "right": lit(4)}}]
    tarjeta(p, x, y, w, h, medida, 9, tinta=tinta_hex, negrita=True, cont=cont)


def texto(p, x, y, w, h, filas):
    ps = [{"textRuns": [{"value": t, "textStyle": e} for t, e in f]} for f in filas]
    p.poner(x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": ps}}]}},
            {"background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}],
             "visualHeader": [{"properties": {"show": lit(False)}}]})


def mapa(p, x, y, w, h, filas, columnas, valor, fondo, tinta, titulo_medida, tam, relleno):
    obj = {"subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}],
           "grid": [{"properties": {"gridVertical": lit(True), "gridVerticalColor": color(BLANCO), "gridVerticalWeight": lit(3),
                                    "gridHorizontal": lit(True), "gridHorizontalColor": color(BLANCO), "gridHorizontalWeight": lit(3),
                                    "rowPadding": lit(relleno), "outlineColor": color(BLANCO)}}],
           "columnHeaders": [{"properties": {"fontSize": lit(8), "fontColor": color(MUTED), "alignment": lit("Center"),
                                             "outline": lit("None"), "backColor": color(BLANCO), "bold": lit(True)}}],
           "rowHeaders": [{"properties": {"fontSize": lit(8), "fontColor": color(TINTA2), "outline": lit("None"),
                                          "backColor": color(BLANCO), "bold": lit(True)}}],
           "values": [{"properties": {"fontSize": lit(tam), "outline": lit("None")}},
                      {"properties": {"backColor": color_medida(fondo), "fontColor": color_medida(tinta)},
                       "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": ref(M(valor))[0]}}],
           "blankRows": [{"properties": {"showBlankRows": lit(False)}}]}
    q = {"queryState": {"Rows": {"projections": [proy(filas, " ")]}, "Columns": {"projections": [proy(columnas, " ")]},
                        "Values": {"projections": [proy(M(valor), " ")]}}}
    p.poner(x, y, w, h, {"visualType": "pivotTable", "query": q, "objects": obj}, caja(titulo_medida=titulo_medida))
    return p.vis[-1]["name"]


def semanas(p, x, y, w, h):
    f = M("S por día")
    q = {"queryState": {"Category": {"projections": [proy(C("Calendario", "Semana del calendario"), "Semana")]},
                        "Y": {"projections": [proy(f, "Pacientes por día")]}}}
    obj = {"dataPoint": [{"properties": {"fill": color_medida("S color")},
                          "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
           "labels": [{"properties": {"show": lit(True), "fontSize": lit(8), "color": color(TINTA), "labelDisplayUnits": lit(1)}}],
           "valueAxis": [{"properties": {"show": lit(False), "gridlineShow": lit(False)}}],
           "categoryAxis": [{"properties": {"fontSize": lit(8), "labelColor": color(TINTA2), "showAxisTitle": lit(False),
                                            "axisType": lit("Categorical"), "innerPadding": lit(25)}}],
           "legend": [{"properties": {"show": lit(False)}}]}
    p.poner(x, y, w, h, {"visualType": "clusteredColumnChart", "query": q, "objects": obj}, caja(titulo_medida="S título"))
    return p.vis[-1]["name"]


def barras(p, x, y, w, h):
    f = M("A barra")
    q = {"queryState": {"Category": {"projections": [proy(C("Aseguradora", "Grupo"), " ")]},
                        "Y": {"projections": [proy(f, "Pacientes")]}},
         "sortDefinition": {"sort": [{"field": f, "direction": "Descending"}], "isDefaultSort": False}}
    obj = {"dataPoint": [{"properties": {"fill": color(BARRA)}}],
           "labels": [{"properties": {"show": lit(True), "fontSize": lit(9), "color": color(TINTA), "labelDisplayUnits": lit(1)}}],
           "valueAxis": [{"properties": {"show": lit(False), "gridlineShow": lit(False)}}],
           "categoryAxis": [{"properties": {"fontSize": lit(9), "labelColor": color(TINTA2), "showAxisTitle": lit(False),
                                            "innerPadding": lit(35)}}],
           "legend": [{"properties": {"show": lit(False)}}]}
    p.poner(x, y, w, h, {"visualType": "clusteredBarChart", "query": q, "objects": obj},
            caja(titulo_medida="T Aseguradoras título", sub="rango probable  ·  probabilidad"))


def panel(p, x, y, w, h):
    """Fondo blanco con borde redondeado, detrás de varias piezas que forman una sola tarjeta."""
    p.poner(x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": " "}]}]}}]}},
            caja())


def medidor(p, x, y, w, h):
    """Sin marca de objetivo: su etiqueta («50 %») salía suelta encima del arco."""
    q = {"queryState": {"Y": {"projections": [proy(M("D prob más"), "Probabilidad")]},
                        "MinValue": {"projections": [proy(M("D cero"))]}, "MaxValue": {"projections": [proy(M("D uno"))]}}}
    obj = {"dataPoint": [{"properties": {"fill": color_medida("D pregunta color")}}],
           "calloutValue": [{"properties": {"show": lit(True), "fontSize": lit(20), "color": color(TINTA), "labelPrecision": lit(0)}}],
           "labels": [{"properties": {"show": lit(False)}}], "targetLabel": [{"properties": {"show": lit(False)}}]}
    p.poner(x, y, w, h, {"visualType": "gauge", "query": q, "objects": obj}, caja(titulo_medida="D pregunta título", fondo=False, borde=False))


def filtro(p, x, y, w, h):
    obj = {"data": [{"properties": {"mode": lit("Dropdown")}}],
           "header": [{"properties": {"show": lit(True), "text": lit("ASEGURADORA"), "fontColor": color(AZUL_SES), "textSize": lit(9),
                                      "bold": lit(True)}}],
           "selection": [{"properties": {"selectAllCheckboxEnabled": lit(True)}}]}
    p.poner(x, y, w, h, {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proy(C("Aseguradora", "Grupo"))]}}},
                         "objects": obj}, caja())


def pagina():
    p = Pagina("Pronóstico de triages", 720)
    W = 1280 - 2 * 16; X0 = 16
    # encabezado
    texto(p, X0, 2, 600, 44, [[("PRONÓSTICO DE TRIAGES", {"fontWeight": "bold", "fontSize": "20pt", "color": AZUL_SES})]])
    tarjeta(p, X0, 40, 600, 22, "T Subtítulo", 9, tinta=MUTED, cont=caja(fondo=False, borde=False))
    filtro(p, 1280 - 16 - 240, 4, 240, 64)
    # fila 1: el día, la pregunta, las semanas
    y1, h1 = 72, 140
    tarjeta(p, X0, y1, 300, h1, "D rango corto", 30, titulo_medida="D título día", negrita=True)
    pildora(p, X0 + 60, y1 + h1 - 32, 180, 24, "D píldora", ROJOS[0], ROJOS[4])
    panel(p, X0 + 300 + G, y1, 260, h1)
    medidor(p, X0 + 300 + G, y1, 260, h1 - 30)
    tarjeta(p, X0 + 300 + G + 40, y1 + h1 - 34, 180, 28, "D pregunta respuesta", 11, tinta_medida="D pregunta color", negrita=True,
            cont=caja(fondo=False, borde=False))
    xs = X0 + 300 + G + 260 + G
    sem = semanas(p, xs, y1, 1280 - 16 - xs, h1)
    # fila 2: calendario | aseguradoras
    y2 = y1 + h1 + G; h2 = 246; wc = 620
    cal = mapa(p, X0, y2, wc, h2, C("Calendario", "Semana etiqueta"), C("Calendario", "Día semana"), "T Calendario celda",
               "T Calendario color", "T Calendario texto", "T Título calendario", 10, 4)
    chip = lambda c: ("■", {"color": c, "fontSize": "11pt"})
    texto(p, X0 + wc - 190, y2 + 4, 180, 22, [[("menos ", {"color": MUTED, "fontSize": "8pt"})] + [chip(c) for c in ROJOS]
                                              + [(" más", {"color": MUTED, "fontSize": "8pt"})]])
    barras(p, X0 + wc + G, y2, 1280 - 16 - (X0 + wc + G), h2)
    # fila 3: horas
    y3 = y2 + h2 + G; h3 = 720 - 6 - y3
    hor = mapa(p, X0, y3, W, h3, C("Calendario", "Día corto"), C("Hora", "Franja"), "T Hora celda", "T Hora color", "T Hora texto",
               "T Título horas", 8, 1)
    pildora(p, X0 + W - 200, y3 + 5, 190, 22, "H píldora", ROJOS[0], ROJOS[4])
    return p, [(cal, sem), (hor, sem)]


if __name__ == "__main__":
    raiz = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "prediccion.Report"; paginas = raiz / "definition" / "pages"
    for d in paginas.iterdir():
        if d.is_dir(): shutil.rmtree(d)
    nueva, sin_filtro = pagina(); nueva.escribir(raiz)
    pj = paginas / nueva.id / "page.json"
    d = json.loads(pj.read_text(encoding="utf-8")); d["displayOption"] = "FitToPage"
    d["objects"] = {"background": [{"properties": {"color": color(FONDO), "transparency": lit(0)}}],
                    "outspace": [{"properties": {"color": color(FONDO)}}]}
    # tocar un día o una hora no recorta el gráfico de semanas: sigue mostrando todas
    d["visualInteractions"] = [{"source": s, "target": t, "type": "NoFilter"} for s, t in sin_filtro]
    pj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    (paginas / "pages.json").write_text(json.dumps({"$schema": PGS, "pageOrder": [nueva.id], "activePageName": nueva.id},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{nueva.nombre}: {len(nueva.vis)} visuales ({nueva.id})")
