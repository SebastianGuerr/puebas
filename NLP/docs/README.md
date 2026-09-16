# Documentación de la fase NLP

Fase 1 del proyecto de triage: obtener, a partir de la columna `HCTMOTCON` de
`DIM_TRIAGE`, un motivo de consulta limpio, corregido y normalizado por nota
(`salidas/triage_limpio.csv`), que consumen `embedding/` y `clustering/`.

| Documento | Contenido |
|---|---|
| [PLAN.md](PLAN.md) | Plan de desarrollo: peticiones del propietario, principios, formato de evidencia, protocolo de sesión, política de seguridad, contrato con el resto del proyecto, etapas E0–E7 con ítems y gates |
| [ESTADO.md](ESTADO.md) | Estado por ítem, cambios sin commit, artefactos, problemas conocidos, próximas acciones. **Leer primero.** |
| [INVESTIGACION.md](INVESTIGACION.md) | Síntesis de la literatura y de los recursos: qué se adopta, qué se prueba, qué se descarta |
| [REFERENCIAS.md](REFERENCIAS.md) | Bibliografía, recursos de datos, modelos, software, licencias y obligaciones |
| [ARQUITECTURA.md](ARQUITECTURA.md) | Función de cada archivo de `NLP/`, grafo de dependencias, entradas y salidas, duplicaciones para el refactor, guía de estilo *(E1.2, versión inicial)* |
| [FLUJO.md](FLUJO.md) | Las fases del pipeline, entradas, salidas, constantes y decisiones, con ejemplos sintéticos ejecutados *(E1.3)* |
| [OPERACION.md](OPERACION.md) | Instalación, artefactos, comandos por escenario, errores conocidos *(E1.4)* |
| [decisiones/](decisiones/) | Un registro por decisión técnica medida |
| [bitacora/](bitacora/) | Evidencia de cierre de cada ítem y registro de sesiones |

Regla de mantenimiento: la documentación se actualiza en el mismo ítem que cambia el
código, no después. Cada bitácora de cierre lleva la lista de documentos revisados
(`PLAN.md` §4.4); cada documento termina con una sección `Historial`.

Ejecución rápida (detalle en [OPERACION.md](OPERACION.md)):

```
python -m NLP.nucleo.requisitos      # comprueba artefactos y modelos
python -m NLP.procesar               # corrida normal desde la base de datos
python -m NLP.reparacion.reparar     # reprocesa el CSV existente sin sustituirlo
```

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | E1.1 | Primera versión del índice |
| 2026-09-16 | E1.3, E1.4 | Enlaces a `FLUJO.md` y `OPERACION.md`, ya escritos; sección `Historial` añadida (antes ausente, detectado por `evaluacion/paridad_docs.py`) |
