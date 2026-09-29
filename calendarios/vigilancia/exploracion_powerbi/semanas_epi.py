"""Calendario epidemiologico (regla OPS/MMWR, la que siguen los calendarios del INS):
semanas domingo-sabado; la SE1 termina el primer sabado de enero que tenga >=4 dias de enero
(equivale a: la SE1 es la semana domingo-sabado que contiene el 4 de enero)."""
import datetime as dt
def inicio_se1(anio):
    d = dt.date(anio, 1, 4)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)   # domingo anterior o igual
def semanas(anio):
    return (inicio_se1(anio + 1) - inicio_se1(anio)).days // 7
def semana_epi(fecha):
    a = fecha.year
    if fecha < inicio_se1(a): a -= 1
    elif fecha >= inicio_se1(a + 1): a += 1
    return a, (fecha - inicio_se1(a)).days // 7 + 1
if __name__ == "__main__":
    for a in range(2007, 2028):
        print(a, "SE1 inicia", inicio_se1(a), "semanas", semanas(a), "<-- 53" if semanas(a) == 53 else "")
    print("2026-09-19 ->", semana_epi(dt.date(2026, 9, 19)), "| 2026-01-03 ->", semana_epi(dt.date(2026, 1, 3)), "| 2026-01-04 ->", semana_epi(dt.date(2026, 1, 4)))
