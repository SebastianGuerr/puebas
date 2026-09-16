# Clasificador de tramos: por qué se usa además de los patrones, no en su lugar

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/reduccion.py`,
`_quitar_clasificador()`.

## Pregunta

Los patrones de `reduccion.py` tienen buena precisión pero mala cobertura:
enumeran casos y se escapa el siguiente. ¿El clasificador de `frases.py`
puede sustituirlos, o solo complementarlos?

## Medición

Sobre 400 tramos que ninguna regla supo etiquetar (ni
`MARCADORES_INSTITUCIONALES` ni los patrones de trámite, examen, conducta,
acompañante o antecedentes, ni el léxico clínico), el clasificador
reconoció 110 como administrativos y 144 como clínicos, dejando 146 en zona
gris.

Los 110 administrativos no los cubría ningún patrón y no se parecen entre
sí más que en el tema, por ejemplo:

- "derivan para manejo por hemodinamia"
- "remision del hospital san isidro"
- "paciente valorado con urgenciologo de turno"
- "tuve cita con especialista y el me derivo"

Cada uno habría necesitado su propia expresión regular.

## Decisión y motivo

Los patrones se mantienen: siguen siendo la defensa más barata y más
predecible. El clasificador se añade para cubrir lo que ellos no ven, con
un freno de densidad clínica encima (ver
`decisiones/2026-09-15-clasificador-freno-clinico.md`, que mide el freno
sobre 100 notas reparadas: notas que recuperan motivo 16 → 24, alarmas de
pérdida 11 → 7).

## Qué la invalidaría

Reentrenar el clasificador sobre el gold (E5.5) y medir si sigue habiendo
tramos que ningún patrón cubre; si la zona gris se reduce a casi nada, el
clasificador deja de aportar cobertura nueva sobre los patrones.
