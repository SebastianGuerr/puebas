# Sesión 2026-09-15 — diagnóstico, reparación y plan

Sesión: Claude Code (orquestador) con el propietario. Estado: cerrada. Ítems del plan
afectados: E0.2 (en curso), E1.1 (parcial). El resto de lo hecho es previo al plan y se
consolida en E0.1.

## Secuencia

1. Inventario de hardware: i7-8550U, 16 GB (5,9 GB libres), UHD 620 sin CUDA, 241 GB
   libres. `torch 2.6.0+cpu`. Ollama con `qwen2.5:3b-instruct` y `gemma4:26b`.
2. Medición del CSV existente (8.751 notas): la fase 5 descartaba en media el 19,5 % del
   contenido; 18,1 % de las notas perdían más de la mitad. Ejemplos: el motivo `cifras
   tensionales altas` se perdía y quedaba solo `niega pérdidas vaginales`.
3. Causa raíz: `lexico_clinico.json` inexistente. Reconstruido (`python -m
   NLP.recursos.lexico`, 32.315 formas): descarte medio 0,195 → 0,121; 25,1 % de notas
   recuperan contenido; 9,5 s por 8.751 notas.
4. Segunda causa: `es_core_news_md` no instalado. Instalado. `dipirona`, `losartan`,
   `cefalea`, `gestante` pasan a estar en vocabulario.
5. `lexico_casing.json` construido desde la BD (94.136 notas; 4.843 entradas).
   `clasificador_frases.joblib` entrenado. **Error cometido y corregido**: `python -m
   NLP.reduccion.frases` regeneró `datos/frases_etiquetadas.csv` (curado a mano);
   restaurado con `git checkout`; reentrenado con `frases.entrenar()` sobre los 19.586
   tramos curados (exactitud 0,971).
6. Análisis estático: 11 funciones sin referencia de 587 (un primer detector con umbral
   mal puesto informó 231; corregido). Los imports "sin usar" de `reglas.py` y
   `terminologia.py` son re-exportaciones y se conservan. Eliminados cinco imports
   inertes.
7. Nuevo `nucleo/requisitos.py` (ver `decisiones/2026-09-15-artefactos-y-version-corrector.md`).
8. Nueva fase 2b `fase2_ortografia/coherencia.py` (ver
   `decisiones/2026-09-15-coherencia.md`). Integrada en `procesar.py`. Prueba de extremo
   a extremo con 60 notas: rescató `enferma → informa`.
9. Investigación con dos agentes: técnicas de corrección y evaluación; recursos y
   modelos. Resultado en `INVESTIGACION.md` y `REFERENCIAS.md`. Hallazgo destacado:
   HUMADEX/spanish_medical_ner se basa en `bert-base-cased` (inglés); descartado.
10. Nuevo `reparacion/` para reprocesar el CSV existente. Cuatro iteraciones sobre 100
    notas:
    - la fase 3 no corría (orden de carga) → corregido;
    - sin léxico de frecuencias el corrector dejaba `dolro` y `anuseas` → corregido
      (`cargar_frecuencias`, desde BD);
    - el clasificador de frases descartaba motivos enteros → freno por densidad (ver
      `decisiones/2026-09-15-clasificador-freno-clinico.md`);
    - la métrica de pérdida contaba relleno como terminología → intersección de léxicos.
    Resultado final en 100 notas: 69 intactas, 24 recuperan motivo, 3 ortografía, 4
    alarmas (todas administrativas).
11. `VERSION_CORRECTOR` → 4; caché apartada.
12. Lanzada la reparación completa sobre 9.311 notas en segundo plano (sin `--aplicar`).
13. Inventario del contrato aguas abajo (`PLAN.md` §6) por agente.
14. Redacción de `docs/`: README, PLAN, ESTADO, INVESTIGACION, REFERENCIAS, decisiones
    y esta bitácora. Memoria del asistente actualizada: documentación en `docs/`, no en
    docstrings.

15. Revisión del propietario sobre la primera versión de la documentación: el plan
    tenía menos detalle que lo expuesto en sesión; la investigación no estaba citada ni
    enlazada; faltaba la política de actualización continua. Reescritos `PLAN.md` (v2:
    diagnóstico con cifras, fichas por ítem con criterio numérico y esfuerzo, sección
    4.4 de mantenimiento, historial) e `INVESTIGACION.md` (fuente por fuente con enlace,
    motivo, aplicación y veredicto; matriz de decisiones); enlaces añadidos a todas las
    citas de `REFERENCIAS.md`; `Historial` en cada documento.

## Comandos principales

```
python -m NLP.recursos.lexico
python -m spacy download es_core_news_md
python -m NLP.recursos.casing
python -c "from NLP.reduccion import frases; frases.entrenar()"
python -m NLP.nucleo.requisitos
python -m NLP.procesar --limite 60 --sin-llm
python -m NLP.reparacion.reparar --limite 100
python -m NLP.reparacion.reparar            # completa, en curso
```

## Pendientes que deja

- E0.1: commit (requiere autorización).
- E0.2: revisar el informe de la reparación completa por término.
- E1.2: `ARQUITECTURA.md` (inventario por agente en preparación al cierre).
- Los ejemplos de notas citados en esta bitácora y en `decisiones/` provienen del CSV
  real; antes de cualquier publicación externa deben sustituirse por casos sintéticos
  (principio 7 del plan).
