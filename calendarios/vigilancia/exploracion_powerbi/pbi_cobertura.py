"""Cobertura temporal (solo agregados por año) de las tablas del tablero '006 Vigilancia Rutinaria'."""
import pbi_rutinaria as P
def agg(p, f=0): return {"Aggregation": {"Expression": P.col(p), "Function": f}}
def filtro(campo, val): return [{"Condition": {"In": {"Expressions": [P.col(campo)], "Values": [[{"Literal": {"Value": f"'{val}'"}}]]}}}]
casos = [
 ("Rutinaria 2026", "año", "nmun_proce", ["conteo"]),
 ("995", "año", "nmun_notif", ["SumaDetot_iraext", "tot_exturg", "SumaDetot_irag"]),
 ("998", "año", "nmun_notif", ["Hombres", "Mujeres"]),
 ("salida_para_rutinaria_995 2026", "año", "nmun_notif", ["SumaDetot_iraext", "tot_exturg"]),
]
for tabla, anio, mun, medidas in casos:
    P.T = tabla
    sel = [dict(P.col(anio), Name="anio")] + [dict(agg(m), Name=m) for m in medidas]
    try:
        ref, filas = P.consulta(sel, filtro(mun, "MANIZALES"))
        print(tabla, "| refresco", ref, "|", [tuple(f) for f in filas])
        sel2 = [dict(P.col(anio), Name="anio"), dict(agg("semana", 4), Name="max_semana")]  # 4 = Max
        ref, f2 = P.consulta(sel2, filtro(mun, "MANIZALES"))
        print("   ultima semana por año:", [tuple(x) for x in f2][-4:])
    except Exception as e:
        print(tabla, "ERROR", repr(e)[:200])
