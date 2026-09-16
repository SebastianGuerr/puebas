# Acompañante y modo de llegada: por qué se quitan aunque describan al paciente

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/reduccion.py`
(`RE_ACOMPANANTE`, `RE_LLEGADA`).

## Pregunta

¿Quién acompaña al paciente y cómo llegó al servicio ("en silla de
ruedas", "con acompañante") debe conservarse en el texto de embedding?

## Medición

Salieron de revisar tres notas a mano y contar el patrón en el corpus:

- 1.301 notas (4,6 %): "en compañía de hija", "con acompañante", "traído
  por su esposa".
- 1.107 notas (3,9 %): "en silla de ruedas", "caminando", "en camilla".

En la nota 803472, estos dos bloques eran lo único que sobrevivía al
recorte: el texto de embedding empezaba con "silla de ruedas con
acompañante" antes de llegar a las epistaxis, que es de lo que hablaba la
nota.

## Decisión y motivo

Se quitan los dos bloques, incluido "en silla de ruedas" aunque describa al
paciente: es una condición previa, no el motivo de hoy, y el triage ya la
registra como variable estructurada aparte. Ninguna de las dos frases
distingue notas de cuadros distintos —son casi idénticas entre sí—, que es
la definición de ruido para el agrupamiento posterior.

## Qué la invalidaría

Que una revisión del clustering muestre que el modo de llegada sí
correlaciona con el motivo de consulta en algún subgrupo (por ejemplo,
traumatismos graves); entonces convendría conservarlo como campo
estructurado en vez de quitarlo del texto.
