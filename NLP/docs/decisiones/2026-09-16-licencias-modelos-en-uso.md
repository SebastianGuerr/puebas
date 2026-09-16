# Licencias de los dos modelos que ya están en el proceso
Fecha: 2026-09-16. Ítem del plan: E3.1 (verificación previa a la integración de recursos),
con efecto sobre E4.6 y E5.6. Autor: sesión de ejecución (orquestador).

## Pregunta

¿Los modelos que el pipeline ya usa —`es_core_news_md` de spaCy (fase 2) y
`qwen2.5:3b-instruct` de Ollama (fase 5)— tienen la licencia que `REFERENCIAS.md`
declaraba (MIT y Apache-2.0), y pueden usarse en un entorno institucional?

## Opciones consideradas

1. Dar por buena la licencia registrada en la documentación del 15/09.
2. Verificar cada licencia en el artefacto instalado, no en la memoria ni en un resumen.

Se eligió la segunda: la política §6.2 del plan exige licencia registrada y verificada
antes de integrar, y estos dos modelos entraron sin ese paso.

## Medición (datos, comandos, resultados)

Directorio de trabajo: `C:\Users\ad6708\Documents\puebas`. Fecha: 2026-09-16.

```
.venv/Scripts/python.exe -c "import json,glob; ..."   # meta.json del paquete instalado
```

```
version: 3.7.0 | license: GNU GPL 3.0
  fuente: UD Spanish AnCora v2.8 -> GNU GPL 3.0
  fuente: WikiNER -> CC BY 4.0
  fuente: spaCy lookups data -> MIT
  fuente: Explosion fastText Vectors (cbow, OSCAR Common Crawl + Wikipedia) -> CC0
```

```
ollama show qwen2.5:3b-instruct --license
```

```
Qwen RESEARCH LICENSE AGREEMENT

Qwen RESEARCH LICENSE AGREEMENT Release Date: September 19, 2024
```

Ambas comprobaciones son locales, sobre el artefacto que el proceso carga de verdad, no
sobre una página web.

## Decisión y motivo

1. **`es_core_news_md` es GPL-3.0**, no MIT. El paquete `spacy` sí es MIT; la licencia del
   modelo la fija su corpus de entrenamiento (AnCora). Se **conserva en uso**: la GPL-3.0
   obliga al distribuir, no al usar internamente, y el proyecto no distribuye software. Se
   registra la obligación en `REFERENCIAS.md` §5 para que quien publique un derivado lo
   sepa. Alternativa si algún día hace falta: `es_core_news_sm`/`md` no cambian de
   licencia, así que habría que sustituir la señal de vocabulario por el léxico propio
   (E3.3), que es además lo que el plan quiere por calidad.
2. **`qwen2.5:3b-instruct` está bajo la Qwen Research License, de uso exclusivamente no
   comercial**, no Apache-2.0. El uso en una institución prestadora de servicios de salud
   no es investigación académica, así que **no puede darse por autorizado**. Efecto
   inmediato: la fase 5 no debe usar el extractor por modelo de lenguaje en producción
   mientras el propietario no lo decida (§6.9). En la práctica esto no frena nada hoy:
   `USAR_LLM` solo actúa si Ollama responde, y la reparación completa del 15 y 16 de
   septiembre se hizo con `extractor de Ollama: no`. E5.6 (medir la ganancia marginal del
   extractor) se mantiene, pero su conclusión debe incluir la alternativa de licencia
   permisiva.
3. Las correcciones equivalentes en los modelos **candidatos** (`medspaner` y
   `lcampillos` son CC-BY-NC-4.0, no AGPL-3.0; `IIC/RigoBERTa-*` tienen licencia propia no
   comercial; `ClinLinker-KB-GP` es Apache-2.0) quedan en `REFERENCIAS.md` §3 y §5. Ningún
   modelo de la lista requiere `trust_remote_code`, y varios no publican `safetensors`
   (§6.4 del plan: dejar constancia al cargar un `pytorch_model.bin`).

## Qué la invalidaría

- Que el propietario obtenga de Alibaba una licencia comercial para Qwen, o que se
  sustituya por un modelo de licencia permisiva (por ejemplo, un Llama o Gemma con
  licencia compatible, o un modelo del BSC): entonces E5.6 puede concluir en producción.
- Que spaCy publique el modelo español bajo otra licencia en una versión posterior.
- Que el proyecto pase a distribuirse fuera de la institución: entonces la GPL-3.0 del
  modelo y la GPL-3.0-only de `language-tool-python` dejan de ser inocuas y hay que
  rediseñar esas dos piezas.
