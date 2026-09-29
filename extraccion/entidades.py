"""
Agrupa las ~330 entidades administradoras de DIM_ENTIDAD en tipos con sentido para el
analisis. No habla con SQL Server: solo lee salidas/triage_entidad.parquet.

    python -m extraccion.entidades      escribe salidas/entidades_clasificadas.csv

Por que por nombre y no por ENTTIPENT: el tipo de la base mezcla cosas que no se parecen
(el 11 junta aseguradoras SOAT, prepagadas, la Universidad Nacional y "PARTICULARES").
Las reglas van en orden y gana la primera que encaja. Es un BORRADOR que revisa el
propietario: el CSV de salida trae la regla que clasifico cada entidad.
"""
import re
from pathlib import Path

import pandas as pd

# (grupo, patron). El orden importa: "COOMEVA MEDICINA PREPAGADA" tiene que caer en
# prepagada antes de que "COOMEVA" la lleve a EPS; "SEGUROS DE VIDA" (ARL) antes que SOAT.
REGLAS = [
    ("nueva_eps_complementario", r"NUEVA EPS PLANES COMPLEMENTARIOS"),
    ("nueva_eps", r"NUEVA EMPRESA PROMOTORA|NUEVA EPS"),
    ("sura_eps", r"^EPS SURA"),
    ("particular", r"PARTICULAR"),
    ("prepagada", r"PREPAGADA|COLSANITAS|MEDPLUS|COMPLEMENTARI"),
    ("arl", r"RIESGOS PROFESIONALES|RIESGOS LABORALES|^ARL|POSITIVA|SEGUROS DE VIDA"),
    ("adres_fosyga", r"ADMINISTRADORA DE LOS RECURSOS|FOSYGA|FONDO DE ATENCION EN SALUD"
                     r"|FONDO NACIONAL DE SALUD|FONSAT"),
    ("soat_aseguradora", r"SEGUROS|ASEGURADORA|^LA PREVISORA S\.?A|QBE|ALLIANZ|MUNDIAL DE"
                         r"|SOLIDARIA|EQUIDAD|LIBERTY|HDI|SBS"),
    ("regimen_especial", r"FIDUCIARIA LA PREVISORA|FIDEICOMISOS PATRIMONIOS|COSMITET|UNIVERSIDAD"
                         r"|POLICIA|SANIDAD MILITAR|ECOPETROL|MAGISTERIO|FUERZA|EJERCITO"),
    ("ente_territorial", r"DIRECCION TERRITORIAL|SECRETARIA|MUNICIPIO|ALCALDIA|GOBERNACION"
                         r"|DEPARTAMENTO|REGIONAL DE ASEGURAMIENTO"),
    ("otra_eps", r"EPS|PROMOTORA DE SALUD|SALUD TOTAL|SANITAS|ASMET|MEDIMAS|SALUDCOOP|CAFESALUD"
                 r"|COOMEVA|FAMISANAR|COOSALUD|MALLAMAS|EMSSANAR|CAPITAL SALUD|COMPENSAR|CAPRECOM"
                 r"|SERVICIO OCCIDENTAL|SALUDVIDA|FAMISALUD|SALUD PARA TODOS|INDIGENA|COMFA"),
    ("ips_remitente", r"ASSBASALUD|IPS|\bESE\b|HOSPITAL|CLINICA"),
]


def grupo(nombre):
    """(grupo, regla) de una entidad por su nombre."""
    if not isinstance(nombre, str) or not nombre.strip():
        return "sin_entidad", "sin nombre"
    limpio = re.sub(r"\s+", " ", nombre.upper()).strip(" .")
    for g, patron in REGLAS:
        if re.search(patron, limpio):
            return g, patron
    return "otro", "ninguna regla"


def clasificar(tabla):
    """Anade la columna 'grupo' a una tabla con columna 'entidad'."""
    mapa = {e: grupo(e)[0] for e in tabla["entidad"].drop_duplicates()}
    return tabla.assign(grupo=tabla["entidad"].map(mapa).fillna("sin_entidad"))


def main():
    raiz = Path(__file__).resolve().parents[1]
    t = pd.read_parquet(raiz / "salidas" / "triage_entidad.parquet")
    resumen = (t.groupby(["entidad_oid", "entidad", "tipo_entidad"], dropna=False)["n"].sum()
                .reset_index().sort_values("n", ascending=False))
    g = resumen["entidad"].map(grupo)
    resumen["grupo"], resumen["regla"] = g.str[0], g.str[1]
    resumen.to_csv(raiz / "salidas" / "entidades_clasificadas.csv", index=False)
    tot = resumen.groupby("grupo")["n"].sum().sort_values(ascending=False)
    print((tot / tot.sum() * 100).round(2).to_string())
    print(f"\n{len(resumen)} entidades -> salidas/entidades_clasificadas.csv (revisar)")


if __name__ == "__main__":
    main()
