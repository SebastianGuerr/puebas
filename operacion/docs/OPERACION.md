# La operación semanal del pronóstico de triage

Este documento es para quien mantenga el pronóstico en el hospital cuando ya no esté quien lo construyó. Explica qué
hace cada pieza, **por qué se decidió así** y qué hacer cuando el tablero avisa de algo. El historial completo de
decisiones está en `docs/CONTEXTO.md`.

## Qué es y qué no es

Es una herramienta que **informa** a urgencias de cuántas personas van a pedir triage en los próximos 28 días:
- cómo se reparten en la madrugada, la mañana, la tarde y la noche;
- a qué horas se concentra la demanda;
- de qué aseguradora llegan.

**No asigna turnos.** Urgencias decide el personal con esta información.

## Cómo se usa

| Qué | Comando (desde la carpeta del proyecto) | Cuándo |
|---|---|---|
| Ciclo completo con datos nuevos | `operacion\semanal.cmd` (equivale a `python -m operacion --extraer`) | Una vez por semana, el lunes temprano |
| Ciclo sin bajar datos | `python -m operacion` | Si la extracción la hace otra persona |
| Solo el semáforo | `python -m operacion --estado` | Para revisar sin reentrenar |
| Abrir el tablero | `operacion\tablero.cmd` (equivale a `streamlit run operacion/tablero.py`) | Cuando se quiera mirar |
| Corregir por la red de urgencias, sin reentrenar | Anotar el episodio en `datos/eventos_red.csv` y correr `python -m operacion --ajustar` | El día que un hospital de Manizales anuncie un cierre o una reapertura a una aseguradora |

El ciclo completo tarda unos 2 minutos sin la extracción. Hace seis cosas, en orden:
1. **Extrae los datos (opcional).** Baja de SQL Server solo **conteos agregados**: triages por día, hora, nivel,
   banda de edad y aseguradora. Nunca baja nombres, documentos ni texto clínico. El protocolo está en
   `extraccion/__init__.py`.
2. **Corta el último día.** La extracción corre de día, así que el último día siempre está a medias.
3. **Reentrena** el modelo desde cero con todo lo conocido. La receta es fija y no vuelve a elegir variables.
4. **Predice los 28 días siguientes y los guarda** en `salidas/operacion/corridas/<fecha>_<modelo>/`. Una corrida
   guardada no se rehace: es la prueba de lo que se dijo antes de que pasara.
5. **Verifica** las corridas anteriores contra lo que ya ocurrió (`salidas/operacion/verificacion.parquet`).
6. **Calcula el semáforo** (`salidas/operacion/estado.json`), que el tablero muestra arriba.

### Programarlo para que corra solo

En Windows, con una cuenta que tenga permiso de lectura en la base `DWSES`:

```
schtasks /Create /TN "Pronostico triage" /TR "\"C:\ruta\al\proyecto\operacion\semanal.cmd\"" /SC WEEKLY /D MON /ST 07:00
```

Cada corrida deja su registro en `salidas/operacion/registro.log`.

**Requisito institucional:** la extracción usa la autenticación de Windows de quien corre la tarea. Esa cuenta
necesita permiso de lectura en `DWSES`. Sin él, la tarea puede correr con `python -m operacion` sin `--extraer`, pero
alguien tiene que poner los archivos de `salidas/` al día. El código no puede dar ese permiso.

## Por qué así

**Reentrenar cada semana con receta fija, y no congelar el modelo.** La serie cambia de nivel: subió hasta 2024 y
lleva dos años cayendo, sobre todo por Nueva EPS. Un modelo congelado se desvía; uno entrenado en 2022-2024
sobrepredice 2026 de forma sistemática. Reentrenar con la misma receta no es lo mismo que volver a diseñar el modelo:
- **la receta no cambia sola**;
- **lo único que se actualiza son los datos**.

La validación de 2025-2026 reajustaba cada 4 semanas con esta misma receta. Eso es lo que se midió.

**El modelo C0r, y no el M3s.** C0r usa solo el triage y el calendario de festivos. M3s añade la Feria, las fiestas de
los pueblos, los desastres, la seguridad y la salud pública, pero:
- esos calendarios se mantienen a mano y terminan en 2026: sin quien los actualice, M3s se degrada **sin avisar**;
- en la prueba que corrige por haber elegido entre muchos diseños, M3 no se separa de C0r;
- en la semana prospectiva del 5 al 11 de octubre de 2026, C0r tuvo un error del 7,3 % y M3s del 6,8 %.

M3s sigue disponible con `--modelo M3s` si alguien mantiene sus calendarios.

**28 días.** Con datos semanales, el aviso útil está a 15-21 días. 28 cubre el mes siguiente con margen. Más allá, el
error crece y lo que manda es el estado de la red de salud, que nadie conoce de antemano.

**El reparto del día con 52 semanas y el de aseguradoras con 4.** La forma del día casi no cambia: con más historia se
reparte mejor, y ya está en el límite del azar de las llegadas. La mezcla de aseguradoras cambia rápido: con la
historia más reciente se reparte mejor. Las dos cosas se midieron (`notebooks/reparto.py`,
`notebooks/aseguradoras.py`).

**El calendario de festivos llega a 2030** (`calendarios/calendario_Colombia.csv`). Antes de 2030 hay que
regenerarlo:

```
cd calendarios
python calendario_colombia.py --fin 2035-12-31
```

Después hay que revisar que los festivos nuevos de Colombia estén. La librería `holidays` los trae, pero una ley
nueva puede tardar en llegar.

## La red de urgencias: el registro que se mantiene a mano

**Qué es.** `datos/eventos_red.csv` es la lista de episodios en los que un hospital de Manizales cierra, restringe o
reabre la atención a una aseguradora. El SES es uno más de la lista. El pronóstico la usa para corregir el día y la
semana **sin reentrenar**. Se mide así:
- **cuánto baja o sube Nueva EPS** con cada tipo de episodio, comparada con Sura, que no tiene episodios;
- se aplica **solo mientras el episodio está en curso**;
- **el año no cambia.**

El porqué y la evidencia están en `docs/CONTEXTO.md` (entrada del 2026-10-14) y la regla preregistrada en
`patrones/datos/variables.csv` (fila `red_de_urgencias`).

**Cuándo anotar.** El día en que se **anuncia** un episodio, no cuando empieza, y otra vez cuando se anuncia su fin.
Las fuentes con fecha son:
- los boletines de la Secretaría de Salud en `centrodeinformacion.manizales.gov.co`;
- la sección de salud de La Patria;
- BC Noticias.

**Cómo anotar.** Una fila por episodio:

| Columna | Qué poner |
|---|---|
| `id` | E + número correlativo |
| `prestador` | Nombre corto: SES, Santa Sofía, Avidanti, Infantil, San Isidro, Ospedale… |
| `eps` | `nueva_eps`, `otra_eps` o `todas` (hoy solo cuenta `nueva_eps`) |
| `tipo` | `solo_urgencias_vitales`, `cierre_total`, `cierre_urgencias`, `restriccion_no_urgente`, `alerta_hospitalaria` o `amenaza_sin_ejecutar` |
| `alcance_urgencias` | `si` si las urgencias **no vitales** quedan cerradas para esa EPS; `no` si siguen abiertas; `desconocido` |
| `fecha_inicio` / `fecha_anuncio` | Día en que entra en vigor / día en que se publicó la primera noticia |
| `fecha_fin` / `fecha_anuncio_fin` | Reapertura / día en que se publicó. **En blanco mientras no se sepa:** el modelo supone que sigue |
| `fuente_inicio`, `fuente_fin`, `nota` | URL y una frase con la cita que sostiene las fechas |

**Dos fuentes, cada una para lo suyo (versión 2, en operación desde el 2026-10-14).**
- **Lo que ya pasó lo mide la base.** Los ingresos **no urgentes** de Nueva EPS en el SES caen casi a cero cuando el
  SES la deja solo con urgencias vitales, y vuelven cuando reabre. Se bajan cada semana con la extracción
  (`salidas/ingresos_entidad.parquet`). Si falta ese archivo, el ajuste no se aplica y la operación lo avisa.
- **Lo que viene lo dice el registro:** cierres o reaperturas **anunciados** que todavía no se ven en los datos.

La versión 1 usaba el registro también para el pasado y falló: una fecha de fin mal deducida duplicó a Nueva EPS en
abril de 2026.

**Qué cuenta del registro.** Las filas de Nueva EPS:
- si el prestador es el SES con `solo_urgencias_vitales`, `cierre_total` o `cierre_urgencias` y el episodio empieza
  (o termina) después del último dato, mueve el estado del SES;
- si es otro prestador con `alcance_urgencias = si`, cuenta como un hospital más cerrado, **solo mientras el SES
  atiende a Nueva EPS** (si el SES no la recibe, los pacientes desviados no llegan aquí).

Las alertas y las amenazas no ejecutadas se muestran como contexto, pero no corrigen. Un tipo de episodio que nunca ha
ocurrido no corrige nada hasta que haya pasado al menos dos semanas con datos: no se ajusta por algo que nunca se ha
visto.

**Después de anotar:** `python -m operacion --ajustar` rehace los días que vienen de la última corrida con el registro
de hoy. No reentrena. Guarda `salidas/operacion/corridas/<corrida>/ajustes/<fecha_hora>.parquet` (ninguno se rehace) y
el tablero muestra el último.

**Qué tanto ayuda** (validación de 2025-2026, a 15-21 días): en 2026 el error del día pasa de 11,6 % a 10,2 % y el de
Nueva EPS de 25,6 % a 20,3 %. En julio de 2026, con el cierre anunciado del SES, pasa de 15,2 % a 6,8 %. No anticipa
una reapertura que nadie anunció: esa se ve cuando llegan los datos.

## El semáforo: qué significa y qué hacer

| Señal | Verde | Amarillo | Rojo | Qué hacer |
|---|---|---|---|---|
| Datos | último dato de hace 8 días o menos | 9 a 21 | más de 21 | Revisar si la extracción corrió; mirar `registro.log` |
| Error del día (últimos 28 días verificados) | ≤ 12 % | 12-18 % | > 18 % | Si dura más de dos semanas, buscar un cambio de la red (cierres, convenios) |
| Rango del 80 % (mismos días) | ≥ 65 % dentro | 50-65 % | < 50 % | El rango está siendo demasiado optimista: leer el número como orientativo |
| Nueva EPS | cambio < 20 % | cambio ≥ 20 % | — | Su convenio cambió: el total y el reparto por aseguradora fallan unas semanas |

Los umbrales salen de la validación de 2025-2026: el error del día estuvo entre el 8 y el 12 %, y el rango cubrió
entre el 71 y el 84 %. Solo cuentan los días predichos **antes** de empezar.

**Si el semáforo queda en gris** («sin verificar»), todavía no hay días predichos con dato real. Es normal en las
primeras semanas.

## Lo que no hace bien, dicho de frente

- **Los cambios de convenio de Nueva EPS.** Es la aseguradora más grande. Su volumen salta entre un 30 y un 50 %
  cuando se suspende o se reanuda la atención, y ningún dato del triage lo anticipa: en esos meses su rango acertó el 5 %.
  Desde el 2026-10-14 se registran con fecha en `datos/eventos_red.csv` (ver «La red de urgencias»). La corrección solo
  sirve si alguien mantiene el registro al día.
- **Los días puntuales de pico.** El modelo acierta el nivel de la semana. Decir qué día concreto va a ser
  excepcionalmente alto no le gana al calendario.
- **Las aseguradoras pequeñas por hora.** Con 2 o 3 pacientes de ARL al día, la hora es azar. Se informan por día y
  con rango.

## Archivos

| Archivo | Qué es |
|---|---|
| `operacion/__init__.py` | El ciclo: extraer, predecir, guardar, verificar, semáforo |
| `operacion/__main__.py` | La línea de comandos |
| `operacion/tablero.py` | El tablero de Streamlit. Solo lee `salidas/operacion/`; no reentrena ni toca la base |
| `operacion/semanal.cmd`, `operacion/tablero.cmd` | Lanzadores para Windows |
| `notebooks/semana.py`, `pronostico.py` | Los modelos (C0r y M3s) |
| `notebooks/reparto.py` | El reparto por hora y jornada |
| `notebooks/aseguradoras.py` | El reparto por aseguradora |
| `notebooks/red.py` | El ajuste por la red de urgencias y la cadena total → horas → aseguradoras por hora |
| `datos/eventos_red.csv` | El registro de episodios de la red, escrito a mano |
| `salidas/operacion/corridas/` | Cada predicción guardada. Se versiona en git como constancia de la fecha |
