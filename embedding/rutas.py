"""
Rutas del paquete embedding (fase 4). Misma regla que NLP/rutas.py:
datos/ se edita a mano y se versiona, salidas/ lo escribe un script.
"""

from pathlib import Path

from NLP import rutas as rutas_nlp

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"

# fuente escrita a mano (versionada)
CATALOGO_SINTOMAS = DATOS / "catalogo_sintomas.json"

# entradas que vienen de las fases 1-3
TRIAGE_LIMPIO = rutas_nlp.TRIAGE_LIMPIO
LEXICO_CLINICO = rutas_nlp.LEXICO_CLINICO

# artefactos generados por estructurar.py
TRIAGE_ESTRUCTURADO_JSONL = SALIDAS / "triage_estructurado.jsonl"
TRIAGE_ESTRUCTURADO_JSON = SALIDAS / "triage_estructurado.json"
RESUMEN_ESTRUCTURACION = SALIDAS / "resumen_estructuracion.txt"

SALIDAS.mkdir(exist_ok=True)
