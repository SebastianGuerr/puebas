# -*- coding: utf-8 -*-
"""Comprueba un modulo de prompt SIN llamar al modelo. Desde la raiz del repo:
    python NLP/competencia/verificar.py <ruta_al_modulo.py>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from NLP import banco, fidelidad
from NLP.prompts import v1_7

ruta = sys.argv[1]
construir, version = banco._cargar_prompt(ruta)
m = banco._MODULO
fallos = []
for nombre in ("construir", "posprocesar", "construir_segunda_pasada"):
    if not callable(getattr(m, nombre, None)):
        fallos.append(f"falta {nombre}()")
formato = getattr(m, "FORMATO", None)
if formato not in (None, "motivo", "razonado"):
    fallos.append(f"FORMATO invalido: {formato!r}")
if not isinstance(getattr(m, "OPCIONES", {}), dict):
    fallos.append("OPCIONES debe ser un dict")

# Notas inventadas: no vienen de la muestra.
pruebas = ["paciente refiere dolor de garganta y fiebre desde hace dos dias",
           "remitido de otro municipio para valoracion",
           "me duele la barriga"]
for n in pruebas:
    p = construir(n)
    if n not in p:
        fallos.append("construir() no incluye la nota")
    s = m.construir_segunda_pasada(n)
    if n not in s or s == p:
        fallos.append("construir_segunda_pasada() debe incluir la nota y diferir del prompt normal")
# posprocesar debe ser el de produccion
casos = [("me corte la mano", "herida en mano derecha"), ("remitido de otro municipio", "dolor abdominal")]
for o, s in casos:
    if m.posprocesar(o, s) != v1_7.posprocesar(o, s):
        fallos.append("posprocesar() no es el de v1_7: debe quedar sin cambios")
        break

largo = len(construir(pruebas[0]))
print(f"{version}: FORMATO={formato} OPCIONES={getattr(m, 'OPCIONES', {})} "
      f"prompt de {largo} caracteres (~{largo // 4} tokens; v1.7 tiene {len(v1_7.construir(pruebas[0]))} car.)")
print("OK" if not fallos else "FALLA:\n  " + "\n  ".join(dict.fromkeys(fallos)))
sys.exit(1 if fallos else 0)
