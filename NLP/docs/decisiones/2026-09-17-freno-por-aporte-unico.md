# El freno del clasificador pasa de densidad clínica a aporte único
Fecha: 2026-09-17. Ítem del plan: §4 del handoff (regresión del recorte). Autor: sesión de
comparación contra el CSV del 11/09.

## Pregunta

El propietario comparó `salidas/triage_limpio.csv` (16/09) con `triage_limpio_antiguo.csv`
(11/09) y vio que el sistema nuevo deja pasar el armazón de la nota («ingresa paciente
refiriendo que…», «paciente con…») donde el antiguo entregaba el motivo desnudo («dolor
abdominal»). El handoff §4 ya registraba la caída del recorte y la atribuía a cuatro frenos
del corrector. ¿Cuál de ellos es, y se puede recuperar el recorte sin volver a perder
terminología?

## Medición

6.501 notas comunes a los dos CSV, mismo `OID` y `texto_original` idéntico byte a byte.
Para aislar la fase 5 se corre **cada versión del recortador sobre la misma entrada**
(`texto_normalizado` del CSV nuevo), de modo que lo único que cambia es el código.

Métricas: `recall_clinico` = terminología del original que sobrevive (criterio doble de
`evaluacion/calidad.py`); `relleno_retenido` = palabras no clínicas del original que
siguen ahí; `recorte_medio` = 1 − palabras(salida)/palabras(original).

### Localización del cambio

| Variante (misma entrada) | recall | sin terminología | recorte | costura |
|---|---|---|---|---|
| fase 5 del 11/09 | 0,9598 | 1,73 % | 0,1555 | 3,49 % |
| fase 5 del 16/09 | 0,9736 | 1,21 % | 0,1249 | 5,80 % |
| fase 5 del 16/09 **con el `_quitar_clasificador` del 11/09** | 0,9571 | 2,19 % | 0,1505 | 3,20 % |

La tercera fila reproduce la primera **cifra a cifra** sobre la muestra de 1.500. Todos los
demás patrones de la fase 5 (`RE_TRAMITE`, `RE_REPORTE`, `RE_TEMPORAL`, `RE_DEMOGRAFICO`,
`RE_EXAMEN`, `RE_CONDUCTA`, `RE_ANTECEDENTES`, `RE_ACOMPANANTE`, `RE_LLEGADA`,
`RE_ENCABEZADO`, `RE_PLURIPATOLOGIA`), `MARCADORES_INSTITUCIONALES`, `VACIAS` y
`ARRANQUE_HUERFANO` son **idénticos** entre las dos versiones, y el reparto entre pasada
agresiva y suave apenas se mueve (86,7 % → 83,4 %). **Toda la regresión del recorte vive
dentro de `_quitar_clasificador()`.**

Dentro de esa función hay dos cambios. Separándolos:

| | recall | recorte |
|---|---|---|
| sin freno clínico (solo el separador conservado) | 0,9546 | 0,1523 |
| con freno por densidad (`DENSIDAD_MINIMA = 0,40`) | 0,9689 | 0,1242 |

El responsable es `_protegido_por_clinica()`. Salva el tramo entero en cuanto el 40 % de
sus palabras con contenido está en el léxico clínico, y el léxico da por clínicas `salud`,
`nivel`, `atención` o `solicita` (problema ya registrado en `ESTADO.md` §5). Con eso, un
tramo administrativo puro se salva por las palabras con las que está escrito.

## Decisión

Sustituir el criterio del freno. El tramo que el clasificador marca como administrativo se
tira **salvo que traiga terminología clínica que no aparezca en ningún otro tramo de la
nota**. Si el concepto ya está dicho en otra parte, tirar el tramo no pierde nada; si es el
único sitio donde aparece, se conserva. La bandera `FRENO_CLASIFICADOR` admite `"aporte"`
(por defecto), `"densidad"` (el comportamiento del 16/09) y `"ninguno"`.

Es la misma asimetría de coste de todo el proyecto — perder el motivo de consulta cuesta
más que arrastrar una frase administrativa — pero aplicada a lo que el tramo *aporta*, no a
cómo está redactado.

## Resultado, sobre las 6.501 notas completas

| | recall | sin terminología | con toda | recorte | relleno | costura |
|---|---|---|---|---|---|---|
| CSV del 11/09 en disco | 0,9298 | 3,48 % | 88,62 % | 0,1868 | 0,7794 | 4,15 % |
| CSV del 16/09 en disco | 0,9788 | 0,71 % | 96,05 % | 0,1211 | 0,8440 | 6,25 % |
| fase 5 del 11/09 | 0,9598 | 1,73 % | 92,93 % | 0,1555 | 0,8103 | 3,49 % |
| fase 5 del 16/09 | 0,9736 | 1,21 % | 95,59 % | 0,1249 | 0,8399 | 5,80 % |
| **freno por aporte** | **0,9806** | **0,66 %** | **96,33 %** | **0,1504** | 0,8151 | 3,88 % |

Domina a las dos versiones anteriores: mejor retención que la del 16/09 y el recorte de la
del 11/09, con las costuras de vuelta al nivel antiguo. Coste: 13,1 s contra 7,5 s para las
6.501 notas.

## Lo que esto NO resuelve

El CSV del 11/09 recorta el 18,68 % y la fase 5 del 11/09, corrida sobre la entrada nueva,
solo el 15,55 %. **Esos 3,1 puntos no son de la fase 5**: vienen de las fases 1–3, que hoy
entregan a la fase 5 un texto distinto del que le entregaban el 11/09. Queda sin investigar.

Sigue en pie lo que dice el handoff §5: el sistema recorta, no extrae. Nadie decide todavía
qué parte de la nota es el motivo de consulta; se quitan bloques enumerados y sobrevive el
resto.

## Reproducir

```
python -m NLP.evaluacion.calidad --csv triage_limpio_antiguo.csv \
       --comparar NLP/salidas/triage_limpio.csv
python -m NLP.evaluacion.control
```

## Historial

| Fecha | Cambio |
|---|---|
| 2026-09-17 | Primera versión: localización de la regresión y freno por aporte único |
