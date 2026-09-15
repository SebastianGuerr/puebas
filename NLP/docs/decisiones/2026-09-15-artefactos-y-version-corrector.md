# Artefactos obligatorios, versión del corrector y caché

Fecha: 2026-09-15. Ítem: previo al plan (peticiones P2, P4, P5). Módulos:
`nucleo/requisitos.py`, `procesar.py`.

## Pregunta

Por qué las corridas anteriores produjeron un CSV completo pero equivocado, y cómo
impedir que vuelva a ocurrir sin que nadie lo note.

## Hallazgos

Cuatro artefactos faltaban y cada módulo que los necesitaba seguía adelante en silencio:

| Artefacto | Efecto de su ausencia |
|---|---|
| `salidas/lexico_clinico.json` | `_es_clinica()` devuelve False para toda palabra; `densidad_clinica()` 0,0 para toda oración; `_quitar_institucional()` descarta toda oración de ≥ 8 palabras. Medido: 25,1 % de notas perdían contenido clínico; 18,1 % perdían más de la mitad |
| modelo spaCy `es_core_news_md` | `linguistica.en_vocabulario()` False para toda palabra y `entidades()` vacío; cinco capas de la fase 2 (enmascarado, pesos, sugerencias, terminología, vocabulario) decidían sin la señal que las gobierna |
| `salidas/lexico_casing.json` | no se restauraba ninguna sigla ni se protegía ningún nombre propio aprendido |
| `salidas/clasificador_frases.joblib` | la capa de trámite no enumerado quedaba fuera |

Además, `cache_correcciones.json` conservaba las decisiones tomadas sin spaCy;
reutilizarla reproducía el daño.

## Decisión

1. `nucleo/requisitos.py` distingue artefactos *exigidos* (su ausencia produce un
   resultado completo y equivocado: léxico clínico, léxico externo, catálogo de síntomas,
   diccionario de siglas, modelo spaCy) de *opcionales* (su ausencia deja señal visible:
   casing, clasificador). `procesar.py` se detiene si falta un exigido. Verificado
   ocultando el léxico: la corrida se detiene con el diagnóstico y el comando de arreglo.
2. `VERSION_CORRECTOR` pasa de `3-contexto-por-suma` a `4-con-spacy-y-coherencia`, lo
   que invalida la caché anterior por clave. La caché física se apartó
   (`cache_correcciones.descartada.json`) porque también contenía entradas de versión 4
   generadas por una corrida de reparación sin léxico de frecuencias.
3. Toda regeneración de artefactos queda documentada en `ESTADO.md` §2 con su comando.

## Qué la invalidaría

Nada la invalida; se amplía cuando aparezcan artefactos nuevos (E3, E5.7).
