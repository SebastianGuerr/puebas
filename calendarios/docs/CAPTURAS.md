# Capturas periódicas: las fuentes que no guardan su historia

**Decisión del propietario (2026-10-05).** Varias fuentes clave publican solo **el estado de hoy** y lo
sobrescriben. Lo que se sabía cada semana o cada mes existe únicamente si alguien lo guardó ese día. Para no
depender de acordarse de correr un script, la captura es **automática**: una tarea programada de Windows.

> **2026-10-15: el orquestador sustituye a esta tarea.** `python -m contexto` corre el capturador como su paso
> `capturas` (semanal), junto con el resto de las fuentes, desde la tarea nueva `triage_contexto_diario` (todos los días
> a las 06:30, sin ventana). **La tarea vieja `triage_capturas_semanales` sigue registrada y activa hasta que el
> propietario registre la nueva y la deshabilite** (`schtasks /Change /TN triage_capturas_semanales /DISABLE`): si
> quedaran las dos, solo se duplicaría la captura del lunes, que no guarda nada si no cambió. Comandos y porqué:
> `contexto/docs/CONTEXTO_EXTERNO.md`, «Las tareas programadas». Lo de abajo describe la tarea vieja.

## Cómo funciona

| Pieza | Qué hace |
|---|---|
| `calendarios/capturas.py` | Baja cada fuente. Si su huella (sha256) cambió, la guarda en `calendarios/capturas/<fuente>/` y la anota en `calendarios/capturas/registro.csv`. Si no cambió, solo anota «sin_cambios» |
| `calendarios/capturas.cmd` | Lanza el capturador desde la raíz del repositorio y guarda la salida en `calendarios/capturas/crudo/tarea.log` |
| Tarea de Windows **`triage_capturas_semanales`** | Corre el `.cmd` **cada lunes a las 08:00**. Si el equipo estaba apagado, corre en cuanto vuelve a estar disponible (`StartWhenAvailable`), con un máximo de 2 h |

```
python calendarios/capturas.py              todas las fuentes
python calendarios/capturas.py --solo bdua  una
python calendarios/capturas.py --estado     la última captura de cada fuente, sin descargar
schtasks /Query /TN triage_capturas_semanales /V /FO LIST     ver la tarea
schtasks /Run   /TN triage_capturas_semanales                 correrla ya
schtasks /Delete /TN triage_capturas_semanales /F             quitarla
```

## Las fuentes y por qué cada una

| Fuente | Qué guarda | Por qué no se puede rehacer después |
|---|---|---|
| `powerbi` | Tableros del INS: SIVIGILA de Manizales por evento y semana, IRA con denominador. Usa `calendarios/vigilancia/powerbi.py`; corre si la última foto tiene 6 días o más | El INS reescribe el tablero cada semana, y las últimas semanas cambian con la notificación tardía. Es la única vía al SIVIGILA de 2026: los microdatos llegan ~8 meses tarde |
| `bdua` | Afiliados de Caldas por EPS × municipio × grupo de edad × sexo × estado × tipo de afiliado, contributivo y subsidiado (datos.gov.co `tq4m-hmg2` y `d7a5-cnra`) | **No tiene histórico:** datos.gov.co solo muestra la foto del mes. Es el tamaño de cada EPS en Manizales mes a mes |
| `afiliacion` | Zips mensuales de MinSalud (cifras de afiliación por EPS y municipio). El zip nacional va a `crudo/` (ignorado por git); se versiona solo lo de Caldas | La página muestra los últimos meses; los antiguos se retiran |
| `medidas` | Los Excel de la Supersalud: EPS e IPS en medida preventiva, intervención forzosa, programa de recuperación, liquidación, reestructuración. **Traen datos de persona de los interventores** (nombre, documento, correo, teléfono): el Excel original va a `crudo/` (no se versiona) y se versiona **solo una tabla limpia** con entidad, NIT, ciudad, departamento, clase de medida, resolución y fechas | Solo listan las medidas vigentes. Cuando una medida termina, desaparece |
| `oni` | El índice ENSO de la NOAA; rehace `calendarios/enso_oni.csv` | Sí se puede rehacer, pero así queda al día solo |

**Sin captura automática por ahora:**
- **las quejas por EPS (PQRD) de la Supersalud:** su página no expone enlaces de descarga, y el reporte
  interactivo da 404;
- **los giros de ADRES:** tablero web, falta verificar si se puede exportar.

Quedan como tareas a mano en `docs/HANDOFF.md`.

## Privacidad

Todas son **agregados** publicados por el Estado: conteos por entidad, municipio, edad o semana.

**La excepción son los Excel de medidas de la Supersalud**, que nombran a los interventores. Se detectó el
2026-10-05, antes de subir nada: se guardan en `crudo/` y al repositorio va solo la tabla limpia. `powerbi.py` tiene su propio blindaje: rechaza cualquier columna de persona de los
tableros por evento.

## Primera captura (2026-10-05)

- **BDUA, corte del 2026-10-02:** 473.394 afiliados en Caldas en el contributivo y 435.507 en el subsidiado.
- **Medidas:** 9 Excel de la Supersalud.
- **ONI:** guardado; `enso_oni.csv` rehecho.

---

## Actualización incremental de las fuentes de M3s (2026-10-15)

**Decisión de origen:** `docs/CONTEXTO.md`, 2026-10-15: cada fuente externa del modelo se actualiza sola. Esta
sección cubre los scripts que **ya existían**; los nuevos (eventos, fiestas, desastres, calendario escolar)
están en `ACTUALIZADORES.md`.

### El problema que se encontró al probarlos

Todos los scripts **rehacían el archivo entero** desde la fuente. Medido el 2026-10-15 contra copias del mismo
día, eso reescribe el pasado en silencio:

| Fuente | Qué cambia en el pasado si se rehace todo | Por qué |
|---|---|---|
| NASA POWER (`raw_nasapower.csv`) | 88 días, 2026-05-31 a 2026-08-27; en esos días la correlación con lo anterior es de **0,17 a 0,60** en temperatura y humedad del consenso | Los últimos ~3 meses de NASA son provisionales y se sustituyen por los definitivos |
| Open-Meteo ERA5-Land (`raw_openmeteo.csv`) | Máxima y mínima en ~1.100 y ~800 días de **toda** la serie: +0,05 °C y −0,06 °C de media | Open-Meteo cambió su cálculo diario; la media no cambió |
| `clima_unificado.csv.gz` | Por lo anterior, las 2.432 filas; antes de mayo de 2026 r > 0,996, después hasta r = 0,17 | Además, los factores de escala por mes y los percentiles de las banderas se calculan sobre toda la serie: **solo añadir 49 días** movió 188-569 celdas del pasado por variable (`llovio` en 4 días, `dia_calido` en 12) |
| ERA5 (`clima_completo.csv.gz`) | Mínima en 2.475 días (−0,05 °C) y, con ella, `tmin_7d` y `tmin_cambio` en todas las filas. En las 22 variables del modelo hasta el 2026-09-20: 2.032 celdas de 134.354 cambian más de 0,05 desviaciones, 18 más de 0,2 | Igual que Open-Meteo. Y el ERA5 de los últimos días es provisional: el archivo del 2026-10-05 tenía mínimas de **5,9 y 3,0 °C** el 24 y 25-sep, que el ERA5 corrigió a ~15 °C |
| USGS (`sismos_usgs.csv`) | El sismo del 2026-09-29 pasó de M4,5 a M4,4: deja de ser «fuerte» y `sismo_fuerte_7d` cambia una semana | El USGS revisa magnitud y lugar en los días siguientes |
| NOAA ONI, MinDefensa, festivos, microdatos SIVIGILA | Nada (0 celdas) | — |

### La regla: el pasado escrito no se toca; la cola reciente sí

`calendarios/actualizacion.py` tiene las piezas comunes, y cada script las usa:

- **`fusionar()`**: se conserva lo ya escrito hasta `REABRIR_DIAS` antes de su última fecha; desde ahí manda la
  fuente. Las celdas vacías del pasado sí se rellenan. Las revisiones que la fuente trae para el pasado **no se
  aplican, pero se cuentan** y se imprimen («revisiones del pasado no aplicadas: N»).
- **`proteger()`**: si la fuente no devuelve nada, acaba antes que el archivo, o trae menos filas en el periodo
  que el archivo ya cubría, **se aborta antes de escribir** (`MenosDatos`, código 1).
- **`escribir_si_cambia()`**: si el contenido no cambió, el archivo no se toca. Un `.csv.gz` reescrito cambia de
  bytes aunque el contenido sea idéntico (la cabecera gzip lleva la hora), y eso ensuciaba git en cada corrida.
  La escritura es atómica: archivo temporal y renombrado.
- **`cambios_largo()`**: para las tablas largas de vigilancia, cuántas filas del archivo previo desaparecerían y
  cuántos valores cambiarían.

**Por qué congelar en vez de aceptar el dato mejorado.** Los experimentos publicados (la vara de M3/M3s, los
cuadernos 22-26) se calcularon sobre los archivos tal como estaban. Si cada actualización los mueve, ningún
número publicado es reproducible y nadie se entera. Además, congelar reproduce lo que se sabía en cada fecha, que
es lo que tendrá la operación. **`--rehacer` sigue existiendo** en todos: acepta las revisiones de todo el
pasado. Es una decisión del propietario, no de la tarea programada.

| Fuente | Comando no interactivo | `REABRIR_DIAS` | Tarda | Frecuencia |
|---|---|---|---|---|
| Festivos | `python calendarios/calendario_colombia.py` | — (determinista) | 3 s | mensual: no cambia, pero avisa si alguien acorta el horizonte (hoy 2030) |
| Clima, fuentes | `python calendarios/clima/clima_manizales.py` | 10 | 9 s (antes 73 s: el METAR se bajaba mes a mes desde 2020) | diaria |
| Clima unificado | `python calendarios/clima/clima_unificado.py` | 10 | 3 s | diaria, después del anterior |
| Clima completo | `python calendarios/clima/clima_completo.py` | 10 | 7 s | diaria |
| ENSO | `python calendarios/clima/enso.py` (o la fuente `oni` del capturador) | 186 | 3 s | semanal: la NOAA publica una vez al mes |
| Sismos | `python calendarios/fenomenos/sismos_usgs.py` | 30 | 3 s | diaria |
| Seguridad | `python calendarios/seguridad/mindefensa.py` | 90 | 20-42 s | semanal |
| Power BI del INS | `python calendarios/vigilancia/powerbi.py` (o la fuente `powerbi`) | una carpeta por día | 31 s | semanal |
| Microdatos SIVIGILA | `python calendarios/vigilancia/sivigila.py`, luego `python calendarios/vigilancia/eventos.py --descargar --seleccionados --ultimos 1` y `python calendarios/vigilancia/eventos.py` | se aborta si cambia el pasado | 15 s y 8 s sin descargas nuevas | mensual |
| Capturas | `python calendarios/capturas.py` | — | 42-52 s | semanal |

Todos salen con código distinto de cero si fallan, y el que no tiene nada nuevo dice «sin cambios, no se toca».
Comprobado el 2026-10-15 con una segunda corrida de cada uno: ninguno reescribió nada.

### Arreglos por fuente

- **`clima_manizales.py` escribía en la carpeta desde la que se corría**, no en `calendarios/clima/`: corrido desde
  la raíz, dejaba los `raw_*.csv` sueltos en la raíz, y `clima_unificado.py` seguía leyendo los viejos. Ahora
  escribe junto al script. Lo mismo `calendario_colombia.py`, que escribía `calendario_Colombia.csv` en la
  carpeta actual.
- **El METAR (IEM) devuelve una fila vacía con la fecha de mañana.** Se guardaba, y `clima_unificado.csv.gz`
  acababa un día en el futuro. Ahora se descarta todo lo posterior a hoy.
- **`clima_unificado.csv.gz` no tiene pluviómetro después del 2026-08-25.** `clima_ideam.csv` no lo regenera
  ningún script del repositorio (llegó hecho en el commit 3d68117), así que desde esa fecha la lluvia del
  consenso es solo NASA escalada. La fuente sigue viva: datos.gov.co tiene La Nubia (`0026155110`, conjuntos
  `s54a-sgyg` de lluvia y `sbwg-7ju4` de temperatura) hasta el 2026-10-14. **Resuelto el mismo día**: `calendarios/clima/clima_ideam.py`
  (reconstrucción y acierto en `CLIMA.md`, «El pluviómetro IDEAM al día»). Lo corre el orquestador a diario.
- **`enso.py`, `sismos_usgs.py`, `mindefensa.py`**: incrementales, con `--rehacer`, y `enso.py` ya no ignora un
  error HTTP de la NOAA.
- **`sivigila.py` y `eventos.py`**: `--hasta` era 2025 fijo, así que 2026 no se iba a bajar nunca. Ahora es el año
  en curso (el que no existe da 404 y se salta). Y había una trampa: con un rango de años más corto
  (`--desde 2025`) **reescribían el archivo solo con esos años**. Medido: `sivigila.py --desde 2024` borraba
  174.162 de 203.772 filas, y `eventos.py --desde 2024`, 89.439 de 99.729. Ahora, si la corrida haría desaparecer
  o cambiar una fila que ya estaba, se aborta (código 1) salvo con `--forzar`. Eso cubre también que el INS
  republique un año pasado.
- **`powerbi.py`**:
  - el 2026-10-15 la lista `MenuReporteNivel2` del portal SIVIGILA respondía **500** («Memory gates checking
    failed»: el servidor del INS sin memoria) mientras el Power BI funcionaba. Si la lista falla, se usan las
    claves de la última descarga, guardadas en su `metadatos.json`. Así se congeló la del 2026-10-15;
  - antes, si un tablero fallaba, la carpeta del día quedaba **incompleta** y era justo la que lee
    `notebooks/indices.familias_operativas()` (la última `powerbi/20*`), que se rompía o perdía una familia.
    Ahora se escribe en `_tmp_AAAA-MM-DD` y solo se publica como `AAAA-MM-DD` si todos los archivos bajaron y
    ninguno trae menos filas que la descarga anterior (salvo los de un solo año, que empiezan de cero en enero).
    Si no, va a `powerbi/_parciales/AAAA-MM-DD/` y sale con código 1.
- **`capturas.py`**:
  - salía siempre con código 0 aunque fallaran fuentes: la tarea programada no podía enterarse. Ahora sale con 1
    si alguna anotó `error`, y `capturas.cmd` pasa ese código a la tarea (`exit /b %ERRORLEVEL%`);
  - si `enso.py` fallaba, la fuente `oni` se anotaba como `nuevo`. Ahora es `error`;
  - **medidas**: la Supersalud regenera los Excel aunque la tabla no cambie. El 2026-10-15 los 9 tenían huella
    nueva y 4 tenían la tabla limpia idéntica a la del 2026-10-05. Ahora se compara la tabla limpia con la última
    guardada y, si es igual, se anota `sin_cambios`;
  - la búsqueda de la última foto del Power BI ignora `_parciales` y `_tmp_`.

## Captura del 2026-10-15

Hecha a mano, porque la del lunes 12 no corrió y la del martes 13 se cortó (sección siguiente).

- **Power BI:** carpeta `2026-10-15`, hasta las semanas 39-41 de 2026. Contra la del 05-oct solo cambian filas de
  2026 (notificación tardía: de 1 a 19 filas por archivo).
- **BDUA:** sin cambios (corte 2026-10-02).
- **Afiliación:** nuevo, septiembre de 2026.
- **Medidas:** 5 tablas cambiaron (entre ellas la de EPS intervenidas, que lee `indices.py`); 4 iguales.
- **ONI:** sin cambios; JAS 2026 = +2,16 (El Niño en curso). ASO sale a principios de noviembre.

## Por qué falló la tarea el 2026-10-13 (código −1073741510)

**Lo que pasó**, del registro del Programador de tareas (`Microsoft-Windows-TaskScheduler/Operational`) y del de
sistema:

1. El equipo se apagó de golpe el **viernes 9-oct a las 15:37** (evento 6008, «cierre inesperado») y no volvió a
   encenderse hasta el **martes 13 a las 07:45**. El lunes 12 era festivo.
2. Por `StartWhenAvailable`, la tarea arrancó a las **07:55:14**, nueve minutos después del inicio de sesión
   (evento 114: «no se pudo iniciar como estaba programada… se inició ahora»).
3. Terminó a las **07:55:41: duró 27 segundos**. Código `3221225786` = `0xC000013A` = `STATUS_CONTROL_C_EXIT`.
4. El log solo tiene la línea de inicio y `registro.csv` no tiene ninguna fila del 13: murió durante la primera
   fuente (`powerbi`, que corre en un subproceso).

**La causa.** `0xC000013A` es el código de un proceso de consola al que se le cierra la ventana o se le manda
Ctrl+C. Con Ctrl+C, Python habría dejado un `KeyboardInterrupt` en el log, y no lo hay; no hubo cierre de sesión
ni apagado a esa hora; y 27 s descarta el límite de 2 h. Lo que queda es **la ventana**: la tarea está como «Solo
interactivo» (`LogonType = InteractiveToken`), así que `cmd.exe` se abre como una **ventana negra visible** en el
escritorio nueve minutos después de encender el equipo, y quien la ve la cierra. Es una inferencia: el registro no
dice quién la cerró, pero es la única explicación compatible con todo lo anterior.

**Lo que no fue:** la batería (`DisallowStartIfOnBatteries` y `StopIfGoingOnBatteries` ya están en `false`), el
límite de 2 h, ni la inactividad (`RunOnlyIfIdle` no está activado; el bloque `IdleSettings` es el de por defecto).

**La configuración que se propone** (la aplica el orquestador en la fase 2; aquí no se tocó la tarea):

| Ajuste | Hoy | Propuesto | Por qué |
|---|---|---|---|
| Ventana | `cmd.exe` visible | Sin ventana: `LogonType = S4U` («ejecutar tanto si el usuario inició sesión como si no», sin guardar contraseña), o lanzar oculto (`conhost.exe --headless` o `pythonw.exe`) | Que no haya nada que cerrar. S4U no tiene credenciales de red del dominio, pero aquí solo se sale a internet; hay que comprobar que `truststore` sigue viendo el certificado de la inspección TLS del hospital |
| Red | sin condición | `RunOnlyIfNetworkAvailable = true` | El 13 arrancó con la red recién levantada (NETLOGON 5719 a las 07:47) |
| Reintento | ninguno | `RestartOnFailure`: 3 intentos cada 30 min | Hoy, si falla, la siguiente oportunidad es dentro de una semana |
| Inicio tras perderse | `StartWhenAvailable`, inmediato | igual, con 15 min de retraso tras el inicio de sesión | Que no compita con el arranque ni con la red |
| Despertar | no | `WakeToRun = true` | Los lunes el portátil puede estar suspendido (no sirve si está apagado) |
| Código de salida | se perdía | ya llega (`exit /b %ERRORLEVEL%`) | Para que «Último resultado» distinga fallo de éxito |
| Historial | activado | igual | Es lo que permitió este diagnóstico |
