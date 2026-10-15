"""
Calendario natural de Colombia.

Genera una dimensión de fechas (una fila por día) con festivos oficiales,
festividades culturales y estructura laboral.

    python calendarios/calendario_colombia.py      escribe calendarios/calendario_Colombia.csv (2020 a 2030)
    python calendarios/calendario_colombia.py --inicio 2020-01-01 --fin 2030-12-31 --salida otro.csv

Por defecto escribe junto a este script, se corra desde donde se corra (antes escribia en la carpeta actual).
Se niega a escribir un calendario mas corto que el que ya hay, y no toca el archivo si no cambio.

Dependencias:
    pip install pandas holidays pyarrow
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import holidays
import pandas as pd
from dateutil.easter import easter

NOMBRE_DIA = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
              4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

NOMBRE_MES = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
              5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
              9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}


# ---------------------------------------------------------------------------
# Atributos temporales
# ---------------------------------------------------------------------------
def _atributos_base(cal: pd.DataFrame) -> pd.DataFrame:
    cal['anio'] = cal['fecha'].dt.year
    cal['mes'] = cal['fecha'].dt.month
    cal['nombre_mes'] = cal['mes'].map(NOMBRE_MES)
    cal['dia'] = cal['fecha'].dt.day
    cal['dia_semana'] = cal['fecha'].dt.dayofweek
    cal['nombre_dia'] = cal['dia_semana'].map(NOMBRE_DIA)
    cal['dia_anio'] = cal['fecha'].dt.dayofyear
    cal['semana_iso'] = cal['fecha'].dt.isocalendar().week.astype(int)
    cal['trimestre'] = cal['fecha'].dt.quarter
    cal['anio_mes'] = cal['fecha'].dt.to_period('M').astype(str)
    cal['dias_del_mes'] = cal['fecha'].dt.days_in_month
    cal['es_inicio_mes'] = cal['fecha'].dt.is_month_start.astype(int)
    cal['es_fin_mes'] = cal['fecha'].dt.is_month_end.astype(int)
    cal['es_finde'] = (cal['dia_semana'] >= 5).astype(int)
    return cal


# ---------------------------------------------------------------------------
# Festivos oficiales y estructura laboral
# ---------------------------------------------------------------------------
def _festivos(cal: pd.DataFrame) -> pd.DataFrame:
    anios = range(int(cal['anio'].min()), int(cal['anio'].max()) + 1)
    co = holidays.country_holidays('CO', years=anios, language='es')
    
    cal['nombre_festivo'] = cal['fecha'].map(lambda d: co.get(d.date()))
    cal['es_festivo'] = cal['nombre_festivo'].notna().astype(int)

    cal['es_no_laboral'] = ((cal['es_finde'] == 1) | (cal['es_festivo'] == 1)).astype(int)
    cal['es_habil'] = 1 - cal['es_no_laboral']
    cal['es_puente'] = ((cal['es_festivo'] == 1) & (cal['dia_semana'] == 0)).astype(int)
    cal['es_vispera_festivo'] = cal['es_festivo'].shift(-1).fillna(0).astype(int)
    cal['es_post_festivo'] = cal['es_festivo'].shift(1).fillna(0).astype(int)

    bloque = (cal['es_no_laboral'] != cal['es_no_laboral'].shift()).cumsum()
    tam = cal.groupby(bloque)['fecha'].transform('size')
    cal['dias_bloque_no_laboral'] = (tam * cal['es_no_laboral']).astype(int)
    cal['es_fin_semana_largo'] = (cal['dias_bloque_no_laboral'] >= 3).astype(int)

    cal['habil_del_mes'] = (cal.groupby(cal['fecha'].dt.to_period('M'))['es_habil']
                            .cumsum() * cal['es_habil'])
    return cal


# ---------------------------------------------------------------------------
# Festividades culturales
# ---------------------------------------------------------------------------
def _n_esimo(cal, mes, dia_semana, n):
    sub = cal[(cal['mes'] == mes) & (cal['dia_semana'] == dia_semana)].copy()
    sub['orden'] = sub.groupby('anio').cumcount() + 1
    return sub.loc[sub['orden'] == n, 'fecha']


def _ultimo(cal, mes, dia_semana):
    sub = cal[(cal['mes'] == mes) & (cal['dia_semana'] == dia_semana)]
    return sub.groupby('anio')['fecha'].max()


def _festividades(cal: pd.DataFrame) -> pd.DataFrame:
    # Móviles
    cal['es_dia_madre'] = cal['fecha'].isin(_n_esimo(cal, 5, 6, 2)).astype(int)
    cal['es_dia_padre'] = cal['fecha'].isin(_n_esimo(cal, 6, 6, 3)).astype(int)
    cal['es_amor_amistad'] = cal['fecha'].isin(_n_esimo(cal, 9, 5, 3)).astype(int)
    cal['es_dia_ninez'] = cal['fecha'].isin(_ultimo(cal, 4, 5)).astype(int)

    # Fijas
    for col, (m, d) in {'es_san_valentin': (2, 14),
                        'es_dia_velitas': (12, 7),
                        'es_halloween': (10, 31),
                        'es_nochebuena': (12, 24),
                        'es_ano_viejo': (12, 31)}.items():
        cal[col] = ((cal['mes'] == m) & (cal['dia'] == d)).astype(int)

    # Fechas comerciales y culturales importantes
    cal['es_dia_mujer'] = ((cal['mes'] == 3) & (cal['dia'] == 8)).astype(int)
    cal['es_dia_trabajo'] = ((cal['mes'] == 5) & (cal['dia'] == 1)).astype(int)
    cal['es_dia_maestro'] = ((cal['mes'] == 5) & (cal['dia'] == 15)).astype(int)
    cal['es_dia_independencia'] = ((cal['mes'] == 7) & (cal['dia'] == 20)).astype(int)
    cal['es_batalla_boyaca'] = ((cal['mes'] == 8) & (cal['dia'] == 7)).astype(int)

    # Navidad
    cal['es_navidad'] = ((cal['mes'] == 12) & (cal['dia'] == 25)).astype(int)

    # Reyes Magos
    cal['es_reyes_magos'] = ((cal['mes'] == 1) & (cal['dia'] == 6)).astype(int)

    # Inocentes
    cal['es_dia_inocentes'] = ((cal['mes'] == 12) & (cal['dia'] == 28)).astype(int)

    # Halloween ya existe, pero es bueno tener temporada
    cal['es_temporada_halloween'] = (
        (cal['mes'] == 10) &
        (cal['dia'].between(15, 31))
    ).astype(int)

    # Temporada navideña ampliada
    cal['es_temporada_navidad'] = (
        ((cal['mes'] == 12) & (cal['dia'] >= 1))
        | ((cal['mes'] == 1) & (cal['dia'] <= 6))
    ).astype(int)

    # Regreso escolar aproximado
    cal['es_regreso_colegio'] = (
        ((cal['mes'] == 1) & (cal['dia'].between(10, 31))) |
        ((cal['mes'] == 7) & (cal['dia'].between(1, 31)))
    ).astype(int)

    # Día de la Tierra
    cal['es_dia_tierra'] = ((cal['mes'] == 4) & (cal['dia'] == 22)).astype(int)

    # Día del Amor y la Amistad ampliado (semana comercial)
    cal['es_semana_amor_amistad'] = (
        (cal['mes'] == 9) &
        (cal['dia'].between(10, 25))
    ).astype(int)

    # Semana Santa: Domingo de Ramos a Domingo de Resurrección.
    # Se calcula la Pascua directamente en vez de buscar el nombre del festivo,
    # porque holidays devuelve los nombres en el idioma del sistema.
    cal['es_semana_santa'] = 0
    for anio in range(int(cal['anio'].min()), int(cal['anio'].max()) + 1):
        resurreccion = pd.Timestamp(easter(anio))

        domingo_ramos = resurreccion - timedelta(days=7)
        jueves_santo = resurreccion - timedelta(days=3)
        viernes_santo = resurreccion - timedelta(days=2)

        cal.loc[cal['fecha'].between(domingo_ramos, resurreccion),
                'es_semana_santa'] = 1

        cal.loc[cal['fecha'] == domingo_ramos,
                'es_domingo_ramos'] = 1

        cal.loc[cal['fecha'] == jueves_santo,
                'es_jueves_santo'] = 1

        cal.loc[cal['fecha'] == viernes_santo,
                'es_viernes_santo'] = 1

        cal.loc[cal['fecha'] == resurreccion,
                'es_domingo_resurreccion'] = 1

    # Temporadas culturales
    cal['es_novena'] = ((cal['mes'] == 12) & (cal['dia'].between(16, 24))).astype(int)
    cal['es_temporada_fin_anio'] = (((cal['mes'] == 12) & (cal['dia'] >= 16)) |
                                    ((cal['mes'] == 1) & (cal['dia'] <= 6))).astype(int)
    cal['es_quincena'] = ((cal['dia'] == 15) | (cal['es_fin_mes'] == 1)).astype(int)
    cal['es_vacaciones_escolares'] = ((cal['mes'].isin([1, 6, 7])) |
                                      ((cal['mes'] == 12) & (cal['dia'] >= 10)) |
                                      (cal['es_semana_santa'] == 1)).astype(int)
    return cal


# ---------------------------------------------------------------------------
# Etiqueta legible
# ---------------------------------------------------------------------------
ETIQUETAS = [
    ('es_dia_madre', 'Día de la Madre'),
    ('es_dia_padre', 'Día del Padre'),
    ('es_amor_amistad', 'Amor y Amistad'),
    ('es_dia_ninez', 'Día de la Niñez'),
    ('es_halloween', 'Halloween'),
    ('es_nochebuena', 'Nochebuena'),
    ('es_navidad', 'Navidad'),
    ('es_ano_viejo', 'Año Viejo'),
    ('es_dia_velitas', 'Día de las Velitas'),
    ('es_san_valentin', 'San Valentín'),
    ('es_dia_mujer', 'Día Internacional de la Mujer'),
    ('es_dia_trabajo', 'Día del Trabajo'),
    ('es_dia_maestro', 'Día del Maestro'),
    ('es_dia_independencia', 'Independencia de Colombia'),
    ('es_batalla_boyaca', 'Batalla de Boyacá'),
    ('es_reyes_magos', 'Día de Reyes'),
    ('es_dia_inocentes', 'Día de los Inocentes'),
    ('es_dia_tierra', 'Día de la Tierra')
]



def _etiquetar(cal: pd.DataFrame) -> pd.DataFrame:
    cal['evento_calendario'] = cal['nombre_festivo']
    for col, texto in ETIQUETAS:
        vacio = cal['evento_calendario'].isna()
        cal.loc[vacio & (cal[col] == 1), 'evento_calendario'] = texto
    return cal


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def construir_calendario(inicio, fin) -> pd.DataFrame:
    cal = pd.DataFrame({'fecha': pd.date_range(pd.Timestamp(inicio).normalize(),
                                               pd.Timestamp(fin).normalize(),
                                               freq='D')})
    cal = _atributos_base(cal)
    cal = _festivos(cal)
    cal = _festividades(cal)
    cal = _etiquetar(cal)
    return cal


def unir_a_triage(df: pd.DataFrame, cal: pd.DataFrame,
                  col_fecha: str = 'HCTFECTRI') -> pd.DataFrame:
    s = df[col_fecha]
    if not pd.api.types.is_datetime64_any_dtype(s):
        s = pd.to_datetime(s, errors='coerce', dayfirst=True, format='mixed')
    if getattr(s.dt, 'tz', None) is not None:
        s = s.dt.tz_localize(None)

    df = df.copy()
    df[col_fecha] = s
    df['fecha'] = s.dt.normalize()
    df['hora'] = s.dt.hour

    choque = [c for c in cal.columns if c in df.columns and c != 'fecha']
    if choque:
        df = df.drop(columns=choque)
    return df.merge(cal, on='fecha', how='left')


def resumen(cal: pd.DataFrame) -> None:
    print(f'Rango      : {cal.fecha.min():%Y-%m-%d} -> {cal.fecha.max():%Y-%m-%d}')
    print(f'Días       : {len(cal):,}')
    print('\nFestivos por año:')
    print(cal.groupby('anio')['es_festivo'].sum().to_string())
    print('\nDías marcados por bandera:')
    banderas = [c for c in cal.columns if c.startswith('es_')]
    print(cal[banderas].sum().sort_values(ascending=False).to_string())


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Calendario natural de Colombia')
    ap.add_argument('--inicio', default='2020-01-01')
    ap.add_argument('--fin', default='2030-12-31')   # 2026-10-13: hasta 2030 para que la operacion no se rompa en enero
    ap.add_argument('--salida', default=str(Path(__file__).resolve().parent / 'calendario_Colombia.csv'))
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from calendarios.actualizacion import escribir_si_cambia, proteger
    calendario = construir_calendario(args.inicio, args.fin)
    viejo = pd.read_csv(args.salida, usecols=['fecha']) if Path(args.salida).exists() else None
    proteger(viejo, calendario, 'fecha', Path(args.salida).name, tolerancia=0)
    escrito = escribir_si_cambia(calendario, args.salida, index=False, encoding='utf-8-sig')
    resumen(calendario)
    print(f'\n{"Guardado en" if escrito else "Sin cambios, no se toca"} {args.salida}')
