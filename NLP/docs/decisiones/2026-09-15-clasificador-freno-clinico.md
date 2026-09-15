# Fase 5: freno por densidad clínica al clasificador de frases

Fecha: 2026-09-15. Ítem: previo al plan (petición P5). Módulo:
`reduccion/reduccion.py`, función `_quitar_clasificador`.

## Pregunta

El clasificador de frases (`clasificador_frases.joblib`) no existía en las corridas
anteriores y se activó por primera vez hoy. Al reprocesar 100 notas descartó tres motivos
de consulta completos. Cómo mantener su aporte (cubre trámite que los patrones no
enumeran) sin que descarte contenido clínico.

## Opciones consideradas

1. Desactivar el clasificador.
2. Exigir un número mínimo de términos clínicos según `depuracion.terminos_clinicos`.
3. Exigir que el tramo tenga densidad clínica ≥ `DENSIDAD_MINIMA` (0,4) según el léxico
   curado del propio módulo, el mismo criterio de `_quitar_institucional`.

## Medición

Tramos descartados por el clasificador y recuperados por cada opción:

| Tramo (anonimizado) | Opción 2 (≥ 2 términos, léxico de depuración) | Opción 3 (densidad ≥ 0,4) |
|---|---|---|
| `... olor fétido por herida quirúrgica a nivel axilar izquierdo` | no (solo reconoce `herida`) | sí (densidad 1,00) |
| `... desviación de la comisura labial lado izquierdo, imposibilidad para cerrar párpado` | no | sí |
| `gestante 11 semanas 1 día; ...` | no | sí (0,67) |

Controles que deben seguir descartándose con la opción 3: `se deriva a valoración por
consulta prioritaria`, `ingresa paciente en camilla. explico al paciente quien comprende
y acepta`, `entidad promotora de salud responde por los niveles de atención` → los tres
descartados.

Efecto en la muestra de 100 notas reparadas: notas que recuperan motivo 16 → 24;
alarmas de pérdida 11 → 7 (todas administrativas tras revisión).

## Decisión y motivo

Opción 3. El clasificador propone; la densidad clínica del tramo verifica, con el mismo
léxico y el mismo umbral que el filtro institucional, para que las dos defensas del
módulo no se contradigan. La opción 2 falla porque `depuracion.py` usa un léxico más
estrecho a propósito.

## Qué la invalidaría

Que el clasificador reentrenado con el gold (E5.5) no descarte contenido clínico por sí
solo; entonces el freno sería redundante y se mediría si conviene quitarlo.
