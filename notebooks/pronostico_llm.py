"""
Experimento del cuaderno 15, a pedido del propietario: ¿puede un modelo de lenguaje medico (MedGemma)
pronosticar el triage? No se entrena: se le da la historia reciente y el contexto, en texto, y se le
pide el numero de los 7 dias siguientes.

    python notebooks/pronostico_llm.py --modelo medgemma1.5:4b                       Ollama local
    python notebooks/pronostico_llm.py --modelo medgemma:latest --host servidor --cada 14

Diseno (docs/CONTEXTO.md, 2026-10-01):
- origenes de 2026 (los del experimento e2), uno de cada --cada dias;
- ve las ultimas 8 semanas de triage con fecha, dia de la semana y festivos; los 7 dias que vienen con
  su calendario y eventos; y el contexto del dia del origen: IRA de Manizales, clima, Nueva EPS y
  desastres, en palabras. Es la misma informacion que tienen los demas modelos en E2;
- temperatura 0, una respuesta: da un PRONOSTICO PUNTUAL, no una distribucion. Se compara solo el error
  del numero, en los mismos origenes que los demas;
- solo agregados diarios: no sale ningun dato de paciente. El servidor del superior (NLP/modelo.py) se usa
  con pocas consultas, por pedido del propietario.

Escribe salidas/pronostico/e2/llm_<etiqueta>.parquet con el formato de los demas (los 9 cuantiles
iguales a la prediccion puntual).
"""
import argparse, json, re, sys, time, urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import pronostico as pr

HOSTS = {"local": "http://127.0.0.1:11434", "servidor": "http://172.16.121.14:8080"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
NOMBRE_CAL = {"es_festivo": "festivo", "es_puente": "puente", "es_semana_santa": "Semana Santa",
              "es_temporada_navidad": "temporada de Navidad", "es_temporada_fin_anio": "fin de año",
              "es_vacaciones_escolares": "vacaciones escolares", "es_quincena": "quincena"}
NOMBRE_FUT = {"fut_ev_feria": "Feria de Manizales", "fut_ev_religioso": "evento religioso", "fut_ev_civico": "evento cívico",
              "fut_ev_cultural": "evento cultural", "fut_ev_deportivo": "evento deportivo",
              "fut_fiestas_cerca": "fiestas en un pueblo cercano", "fut_dia_madre": "día de la madre",
              "fut_dia_padre": "día del padre", "fut_amor_amistad": "amor y amistad", "fut_dia_velitas": "día de velitas",
              "fut_halloween": "Halloween", "fut_nochebuena": "Nochebuena", "fut_navidad": "Navidad", "fut_ano_viejo": "Año Viejo"}


def etiqueta(d, cal, FUT):
    marcas = [v for k, v in NOMBRE_CAL.items() if cal.at[d, k] == 1]
    marcas += [v for k, v in NOMBRE_FUT.items() if FUT.at[d, k] > 0]
    return f"{d.date()} ({DIAS[d.dayofweek]}{', ' + ', '.join(marcas) if marcas else ''})"


def pct(x):
    return f"{(np.exp(x) - 1) * 100:+.0f} %"


def contexto_texto(PAS, o):
    p = PAS.loc[o]
    lineas = [
        f"- Consultas por infección respiratoria (IRA) en Manizales la semana pasada: {pct(p.ext_sal_ira_total)} frente al último año"
        f" (niños de 0 a 4 años: {pct(p.ext_sal_ira_0_4)}; mayores de 60: {pct(p.ext_sal_ira_60)}).",
        f"- Clima de la última semana frente a lo normal del mes: temperatura {p.ext_cli_temp_7d:+.1f} °C, humedad {p.ext_cli_humedad_7d:+.1f} puntos,"
        f" lluvia {pct(p.ext_cli_lluvia_7d)}.",
        f"- Pacientes de Nueva EPS (la aseguradora más grande del hospital) en las últimas 4 semanas: {pct(p.ext_red_nueva_cambio)} frente a las 4 anteriores.",
        f"- Lesiones personales en la ciudad la última semana: {pct(p.ext_soc_lesiones_personales)} frente al último año.",
    ]
    if p.ext_cat_desastre > 0: lineas.append("- Hay una emergencia o desastre activo en la ciudad.")
    return "\n".join(lineas)


def prompt(y, cal, PAS, FUT, o):
    hist = "\n".join(f"{etiqueta(d, cal, FUT)}: {'sin dato' if np.isnan(v) else int(v)}"
                     for d, v in y.loc[o - pd.Timedelta(days=55):o].items())
    fut = "\n".join(etiqueta(o + pd.Timedelta(days=h), cal, FUT) for h in range(1, pr.H + 1))
    return ("Eres un analista de demanda hospitalaria. Esta es la serie diaria de solicitudes de triage de urgencias de "
            "un hospital de Manizales, Colombia, en las últimas 8 semanas:\n\n"
            f"{hist}\n\nContexto de la ciudad al día de hoy ({o.date()}):\n{contexto_texto(PAS, o)}\n\n"
            f"Pronostica cuántas solicitudes de triage habrá en cada uno de estos 7 días:\n\n{fut}\n\n"
            "Responde SOLO con 7 números enteros separados por comas, en el mismo orden, sin texto adicional.")


def preguntar(host, modelo, texto):
    cuerpo = json.dumps({"model": modelo, "prompt": texto, "stream": False, "think": False,
                         "options": {"temperature": 0, "num_predict": 80, "num_ctx": 4096}}).encode()
    r = urllib.request.urlopen(urllib.request.Request(HOSTS[host] + "/api/generate", cuerpo,
                                                      {"Content-Type": "application/json"}), timeout=900)
    return json.loads(r.read())["response"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True); ap.add_argument("--host", default="local", choices=list(HOSTS))
    ap.add_argument("--cada", type=int, default=7); ap.add_argument("--muestra", action="store_true", help="imprime un prompt y sale")
    a = ap.parse_args()
    pr.usar("e2"); y, cal = pr.cargar()
    PAS, FUT = pr.contexto(cal.index)
    ors = pr.origenes()[::a.cada]
    if a.muestra:
        print(prompt(y, cal, PAS, FUT, ors[len(ors) // 2])); sys.exit()
    tag = "llm_" + re.sub(r"[^a-z0-9]", "", a.modelo.split(":")[0].lower()) + "_" + a.host
    filas, t0 = [], time.time()
    for i, o in enumerate(ors):
        try:
            resp = preguntar(a.host, a.modelo, prompt(y, cal, PAS, FUT, o))
        except Exception as e:
            resp = f"ERROR {e!r}"
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", resp)][:pr.H]
        ok = len(nums) == pr.H
        for h in range(1, pr.H + 1):
            t = o + pd.Timedelta(days=h); v = nums[h - 1] if ok else np.nan
            filas.append({"modelo": tag, "origen": o, "h": h, "fecha": t, "real": y.get(t, np.nan),
                          "respuesta_valida": ok, **{c: v for c in pr.QCOL}})
        print(f"{i + 1}/{len(ors)} {o.date()} {'ok ' + str([int(n) for n in nums]) if ok else 'NO VALIDA: ' + resp[:80]!r} ({time.time() - t0:.0f} s)", flush=True)
    d = pd.DataFrame(filas)
    car = pr.EXP["carpeta"]; car.mkdir(parents=True, exist_ok=True)
    d.to_parquet(car / f"{tag}.parquet")
    print(f"{tag}: respuestas validas {d.drop_duplicates('origen').respuesta_valida.mean():.0%}")
