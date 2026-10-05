"""
Fechas marcadas para el entrenamiento curado (fila entrenamiento_curado de patrones/datos/variables.csv).

    import marcas
    M = marcas.marcar(dias)       # una columna booleana por tipo de contexto, y 'estable' = ninguna

Las marcas salen SOLO del calendario y de las variables externas, nunca del triage: marcar los picos del propio
desenlace ensenaria al modelo a esperar picos. Cada tipo marca lo excepcional (del orden del 5-15 % de los dias): los umbrales
se fijaron solo con la frecuencia de cada evento y percentiles de 2020-2024, sin mirar el triage ni 2025-2026.
"""
import numpy as np
import pandas as pd

import indices as ix
import pronostico as pr

TIPOS = ["calendario especial", "transición de clima", "clima extremo", "ola de salud pública", "red de salud",
         "El Niño / La Niña fuerte", "sismo", "COVID"]


def marcar(dias):
    dias = pd.DatetimeIndex(dias)
    cal = (pd.read_csv(pr.RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
             .reindex(dias)[pr.CAL].apply(pd.to_numeric, errors="coerce").fillna(0))   # sin pr.usar(): no cambia el experimento
    H = ix.contexto_holistico(dias).reindex(dias)
    R = ix.regimenes_diarios().reindex(dias).fillna(0)
    cl = ix.clima_diario().reindex(dias)
    ref = lambda s, desde="2010-01-01": s.loc[desde:"2024-12-31"]
    cambio = H[["ext_h_cambio_1", "ext_h_cambio_2", "ext_h_cambio_3"]].abs()
    u_cambio = ref(cambio, "2020-01-01").quantile(.95)
    u_red = ref(H.ext_h_cambio_nueva_eps_28d.abs(), "2020-01-01").quantile(.95)
    otras = {"ext_h_fam_violencias_y_agresiones": 1.5, "ext_h_fam_salud_mental_e_intoxicaciones": 1.5,
             "ext_h_fam_materno_perinatal": 1.5, "ext_h_fam_inmunoprevenibles": 2.0}
    M = pd.DataFrame(index=dias)
    M["calendario especial"] = cal[["es_festivo", "es_puente", "es_vispera_festivo", "es_post_festivo", "es_semana_santa",
                                    "es_temporada_fin_anio"]].max(axis=1) > 0
    M["transición de clima"] = (cl.seco_a_lluvioso.rolling(7, min_periods=1).max() > 0) | (cambio > u_cambio).any(axis=1)
    M["clima extremo"] = (H.ext_h_racha_seca > 14) | (cl.semana_muy_lluviosa > 0)
    M["ola de salud pública"] = (H.ext_h_fam_respiratoria > 1) | pd.concat([H[c] > u for c, u in otras.items()], axis=1).any(axis=1)
    M["red de salud"] = (H.ext_h_resolucion_nueva_eps_30d > 0) | (H.ext_h_cambio_nueva_eps_28d.abs() > u_red)
    M["El Niño / La Niña fuerte"] = R.oni.abs() >= 1.5
    M["sismo"] = R.sismo_fuerte_7d > 0
    M["COVID"] = (R.covid_fuerte + R.covid_parcial) > 0
    M = M.fillna(False).astype(bool)
    M["estable"] = ~M[TIPOS].any(axis=1)
    return M
