# Documentación de la fase NLP

Fase 1 del proyecto de triage: obtener, a partir de la columna `HCTMOTCON` de
`DIM_TRIAGE`, un motivo de consulta limpio, corregido y normalizado por nota
(`salidas/triage_limpio.csv`), que consumen `embedding/` y `clustering/`.

| Documento | Contenido |
|---|---|
| [HANDOFF.md](HANDOFF.md) | **Empezar por aqui.** Que se consiguio, que se rompio y que sigue sin resolverse |
| [archivo/](archivo/) | **Cerrado.** Plan, investigación y guía de anotación de la sesión del 15–16/09. Se conservan como historial de lo que se intentó y de lo que no sirvió |
| [ESTADO.md](ESTADO.md) | Estado por ítem, cambios sin commit, artefactos, problemas conocidos, próximas acciones. **Leer primero.** |
| [REFERENCIAS.md](REFERENCIAS.md) | Bibliografía, recursos de datos, modelos, software, licencias y obligaciones |
| [ARQUITECTURA.md](ARQUITECTURA.md) | Función de cada archivo de `NLP/`, grafo de dependencias, entradas y salidas, duplicaciones para el refactor, guía de estilo *(E1.2, versión inicial)* |
| [FLUJO.md](FLUJO.md) | Las fases del pipeline, entradas, salidas, constantes y decisiones, con ejemplos sintéticos ejecutados *(E1.3)* |
| [OPERACION.md](OPERACION.md) | Instalación, artefactos, comandos por escenario, errores conocidos *(E1.4)* |
| [decisiones/](decisiones/) | Un registro por decisión técnica medida |
| [bitacora/](bitacora/) | Evidencia de cierre de cada ítem y registro de sesiones |

Regla de mantenimiento: la documentación se actualiza en el mismo ítem que cambia el
código, no después. Cada bitácora de cierre lleva la lista de documentos revisados
(`archivo/PLAN.md` §4.4); cada documento termina con una sección `Historial`.

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
