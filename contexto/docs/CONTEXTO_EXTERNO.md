# El contexto externo: cómo se mantiene solo

**Para quien lo mantenga cuando el practicante ya no esté.** Este documento dice qué hace el orquestador, por qué
cada fuente se actualiza cada cuánto, cuándo una fuente está «atrasada» y qué hacer cuando algo se pone en rojo.

**Decisión de origen:** `docs/CONTEXTO.md`, 2026-10-15: el contexto externo de M3s se actualiza solo, un orquestador
corre todas las fuentes y una tarea programada lo lanza. Los actualizadores de cada fuente están descritos en
`calendarios/docs/CAPTURAS.md` (los que ya existían) y `calendarios/docs/ACTUALIZADORES.md` (los nuevos).

## Qué hace, en una frase

`python -m contexto` corre, cada mañana, los actualizadores de las fuentes que **tocan** según su frecuencia; deja
la salida de cada uno en un registro; mide cuán al día está cada fuente (`frescura.csv`, que lee el semáforo de la
operación); y calcula el contexto diario con las funciones del modelo (`contexto_diario.csv`).

| Pieza | Qué es |
|---|---|
| `contexto/__init__.py` | Los pasos, la frescura y el orquestador |
| `contexto/__main__.py` | La línea de comandos |
| `contexto/diario.py` | El contexto diario (`python -m contexto.diario`) |
| `contexto/contexto.cmd` | Lo que corre la tarea diaria: el orquestador desde la raíz, con su código de salida |
| `contexto/operacion_semanal.cmd` | Lo que corre la tarea semanal: `python -m operacion` sin `--extraer` |
| `contexto/oculto.vbs` | Lanza un `.cmd` **sin ventana** y devuelve su código de salida |
| `contexto/triage_contexto_diario.xml` | La tarea diaria, para importar con `schtasks` (no está registrada) |
| `contexto/triage_operacion_semanal.xml` | La tarea semanal, igual |

Todo lo que escribe va a `salidas/contexto/` (no se versiona: se regenera):

| Archivo | Qué guarda |
|---|---|
| `pasos.json` | Por paso: la última corrida (inicio, resultado, código, duración, detalle) y la última **exitosa**. De ahí sale qué toca. Además, la última corrida del orquestador (`orquestador`) |
| `registro/<fecha>.log` | La salida completa de cada paso del día, con cabecera `==== hora paso ====` y cierre `---- paso: resultado` |
| `registro/tarea.log` | Lo que imprime el orquestador cuando lo lanza la tarea (y cualquier error de Python que lo tumbe) |
| `frescura.csv` | Una fila por fuente. Esquema fijo: lo lee `operacion/` |
| `contexto_diario.csv` | Una fila por día, 2020-01-01 al horizonte de los calendarios |
| `por_confirmar_*.csv` | Las listas que escriben los actualizadores de eventos, fiestas, desastres y calendario escolar |

## Cómo se usa

```
python -m contexto                  corre los pasos que tocan (lo que hace la tarea diaria)
python -m contexto --todo           fuerza todos
python -m contexto --solo sismos    uno (o varios: --solo sismos desastres)
python -m contexto --sin-hospital   sin la extracción de SQL Server (fuera del hospital)
python -m contexto --estado         solo imprime la frescura: no corre nada ni escribe nada
python -m contexto --pasos          lista los pasos con su frecuencia
python -m contexto --esperar 90     espera hasta 90 min a que termine la corrida de hoy (lo usa la tarea semanal)
python -m contexto.diario           solo rehace contexto_diario.csv
```

Siempre con `.venv\Scripts\python.exe`, desde la raíz del repositorio.

**Código de salida:** 0 si ningún paso que usa M3s falló; **1** si falló alguno de ellos o el contexto diario; **3** si
ya había otra corrida en curso (el orquestador no se corre dos veces a la vez: lo impide un bloqueo de archivo que el
sistema suelta solo si el proceso muere), o si `--esperar` agotó el tiempo.

## Los pasos

| Paso | Comando | Frecuencia | M3s | Depende de | Por qué esa frecuencia |
|---|---|---|---|---|---|
| `festivos` | `calendarios/calendario_colombia.py` | mensual | sí | — | Es determinista y llega a 2030. Se corre para que falle si alguien acorta el horizonte |
| `clima_fuentes` | `calendarios/clima/clima_manizales.py` | diaria | no | — | Open-Meteo, NASA POWER y el METAR de La Nubia salen cada día. Lo usa M3 (1-7 días), no M3s |
| `clima_ideam` | `calendarios/clima/clima_ideam.py` | diaria | no | — | Pluviómetro de La Nubia en datos.gov.co. **Si el script no existe, el paso queda «omitido: no instalado»**, sin contar como fallo |
| `clima_unificado` | `calendarios/clima/clima_unificado.py` | diaria | no | `clima_fuentes`, `clima_ideam` | El consenso: tiene que correr después de sus fuentes |
| `clima_completo` | `calendarios/clima/clima_completo.py` | diaria | no (indirecto) | — | ERA5. M3s quita el clima de rezago corto, así que sus valores no entran; pero `mecanismos.columnas` lee el archivo y, si faltara, M3s no correría |
| `enso` | `calendarios/clima/enso.py` | semanal | sí | — | La NOAA publica el ONI una vez al mes; semanal basta para no perderlo más de una semana |
| `sismos` | `calendarios/fenomenos/sismos_usgs.py` | diaria | sí | — | `sismo_fuerte_7d` es una ventana de 7 días: un día de retraso es ya 1/7 del efecto |
| `desastres` | `calendarios/fenomenos/actualizar_desastres.py` | diaria | sí | `sismos` | El detector preregistrado de terremotos; mira el mismo catálogo |
| `mindefensa` | `calendarios/seguridad/mindefensa.py` | semanal | sí | — | Publica por mes con 2-6 semanas de rezago; semanal la recoge sin esperar un mes entero |
| `capturas` | `calendarios/capturas.py` | semanal | sí | — | Power BI del INS (semanal), BDUA, afiliación, medidas de la Supersalud y ONI: fuentes que sobrescriben su estado y solo existen si se guardan ese día. El Power BI se baja solo si la última foto tiene 6 días o más |
| `sivigila` | `calendarios/vigilancia/sivigila.py` | mensual | sí | — | Microdatos anuales del INS (~8 meses tarde); mensual sobra para enterarse |
| `sivigila_eventos` | `calendarios/vigilancia/eventos.py --descargar --seleccionados --ultimos 1`, y luego `calendarios/vigilancia/eventos.py` | mensual | sí | — | Igual. El segundo comando solo corre si el primero salió bien. Si la lista `Microdatos` del INS no responde, usa el catálogo guardado y sale con 0 y un `AVISO` (código 1 solo sin catálogo guardado o si movería el pasado; `calendarios/docs/VIGILANCIA.md`) |
| `eventos` | `calendarios/eventos/actualizar_eventos.py` | semanal | sí | — | Proyecta los eventos recurrentes; semanal para que la lista por confirmar no envejezca |
| `fiestas` | `calendarios/eventos/actualizar_fiestas.py` | semanal | sí | — | Lo mismo con las fiestas de Caldas (`fut_m_fiesta_lejana`) |
| `escolar` | `calendarios/actualizar_escolar.py` | mensual | no | — | Recesos escolares estimados; el modelo todavía no los usa |
| `hospital` | `python -m extraccion --series` | diaria | sí | — | Conteos agregados de SQL Server con autenticación de Windows: el desenlace y el estado de la red de urgencias |

**Qué toca.** Un paso toca si nunca tuvo una corrida exitosa, o si la última exitosa tiene al menos tantos días como su
frecuencia (1, 7 o 30). Un paso que falla **no** actualiza su última exitosa, así que vuelve a tocar al día siguiente:
el reintento de un paso semanal o mensual es diario hasta que salga bien.

**Dependencias.** Si un paso falla en una corrida, los que dependen de él no corren en esa corrida y quedan como
`omitido` con el motivo. Solo dos cadenas: el clima (`clima_fuentes` y `clima_ideam` → `clima_unificado`) y
`sismos` → `desastres`. Un `clima_ideam` no instalado no bloquea a `clima_unificado`.

**Resultado de cada paso:**
- `ok`: salió con código 0 y cambió alguna de sus salidas;
- `sin_cambios`: salió con 0 y ninguna salida cambió. Se compara el **contenido** (sha256, descomprimido en los
  `.gz`, cuya cabecera lleva la hora), no la fecha del archivo;
- `fallo`: código distinto de 0, o superó su tiempo límite (entonces se mata el proceso y todos sus hijos);
- `omitido`: no corrió (script no instalado o dependencia fallida).

Cada paso corre en un subproceso sin ventana, con su tiempo límite (de 5 min a 1 h según el paso; 40 min en
capturas y vigilancia, que descargan Excel grandes). Su salida completa va al log del día.

## La frescura (`frescura.csv`)

**Esquema fijo** (lo lee `operacion.contexto_externo()`; no cambiar nombres ni orden de columnas):
`fuente, archivo, ultimo_dato, ultima_corrida, resultado, dias_atraso, atraso_tolerado, nivel, usa_m3s, detalle`.

- `ultimo_dato`: la fecha más reciente **con dato real**, leída del archivo de la fuente, nunca del registro. En
  clima, el último día con la variable principal no vacía (los archivos traen filas vacías de los días que la fuente
  aún no publicó). La única excepción son las medidas de la Supersalud: la fuente solo publica lo vigente, así que el
  último dato es el último día en que se verificó (`calendarios/capturas/registro.csv`).
- `ultima_corrida` y `resultado`: los de la última vez que el paso de esa fuente se intentó (`pasos.json`).
- `dias_atraso` = hoy − `ultimo_dato`. **Negativo en los calendarios**: es la cobertura hacia adelante.
- `atraso_tolerado`: en días. En los calendarios es negativo: «tiene que cubrir al menos tantos días hacia
  adelante».
- `nivel`:
  - **rojo** si el atraso supera el tolerado, si no hay dato o si la última corrida falló;
  - **amarillo** si el atraso supera el umbral de aviso, si el paso quedó omitido, o si no hubo una corrida exitosa
    en 2 × frecuencia + 2 días (el orquestador dejó de correr);
  - **verde** si no.
- `usa_m3s`: si un cambio en esa fuente cambia lo que M3s ve.

**Los umbrales, por cómo publica cada fuente** (el aviso, en amarillo, va entre paréntesis):

| Fuente | Tolerado (aviso) | Por qué |
|---|---|---|
| `festivos` | −365 (−730) | Tiene que cubrir al menos un año hacia adelante. Hoy llega a 2030 |
| `clima_openmeteo` | 10 (8) | ERA5-Land del archivo de Open-Meteo: ~5-7 días de rezago |
| `clima_nasapower` | 10 (7) | NASA POWER: ~3-4 días |
| `clima_iem` | 3 (2) | METAR de La Nubia: tiempo real |
| `clima_ideam` | 15 (10) | datos.gov.co publica La Nubia al día anterior; se deja margen por los cortes del IDEAM |
| `clima_unificado` | 10 (8) | Hereda el rezago de sus fuentes; el último día del consenso |
| `clima_completo` | 10 (8) | ERA5: ~6 días |
| `enso` | 95 (80) | La fecha del ONI es el mes central del trimestre (JAS → 15-ago). El trimestre siguiente sale ~5 semanas después de que acaba: justo antes de esa publicación, el atraso normal llega a ~85 días |
| `sismos` | 260 (—) | Es un catálogo de eventos, no una serie: el atraso es el tiempo desde el último sismo M ≥ 3 a 150 km. El hueco más largo de 2010-2026 fue de 258 días. Más que eso sugiere que el catálogo dejó de llegar |
| `desastres` | — | Catálogo de eventos raros (1 terremoto con daños en seis años): el atraso no mide frescura. Manda la regla de la corrida |
| `mindefensa` | 75 (42) | Publica por mes, con 2-6 semanas de rezago: justo antes de publicar un mes, el atraso normal llega a ~75 días. **El aviso es 42 porque M3s lee el dato de hace 42 días** (`PUBLICACION_MINDEFENSA`): por encima, las columnas sociales del origen quedan vacías y el modelo las trata como faltantes |
| `powerbi` | 24 (17) | El INS actualiza el tablero cada semana con 1-2 semanas de rezago y la captura es semanal: semana epidemiológica (7) + rezago (≤ 10) + captura (7) |
| `bdua` | 45 (35) | Foto mensual sin histórico |
| `afiliacion` | 60 (50) | MinSalud publica el mes M unas 2 semanas después de cerrarlo |
| `medidas` | 14 (9) | Se verifica cada semana |
| `sivigila`, `sivigila_eventos` | 640 (610) | Los microdatos del año Y salen ~8 meses después de cerrarlo: justo antes de que salga 2026 (sep-2027), el último dato es el 03-ene-2026, ~606 días |
| `eventos`, `fiestas`, `escolar` | −180 (−365) | Tienen que cubrir al menos 6 meses hacia adelante. Sus actualizadores proyectan el año en curso y los 2 siguientes |
| `hospital` | 4 (2) | Extracción diaria; un fin de semana largo con el equipo apagado son 3-4 días |
| `contexto_diario` | −180 (−365) | La salida del orquestador. Si falla, las funciones de M3s no corren con los archivos de hoy |

Además, la fila **`por_confirmar`** cuenta los pendientes de `salidas/contexto/por_confirmar_*.csv` que caen en los
próximos 60 días: eventos y fiestas estimados (por `fecha_estimada`), recesos escolares estimados (por
`fecha_inicio`) y, en desastres, las detecciones nuevas (`estado` `nueva_*`) de los últimos 60 días, porque su efecto en
el modelo va hacia adelante. Amarillo si hay alguno; el detalle los nombra. `ultimo_dato` es el más próximo.

## El contexto diario (`contexto_diario.csv`)

Una fila por día, desde el 2020-01-01 hasta el **horizonte de los calendarios**: el fin del último año proyectado en
eventos y en fiestas (sus actualizadores proyectan años enteros), sin pasar del final de `calendario_Colombia.csv`. El
2026-10-15 es el 2028-12-31: 3.288 días.

Columnas, todas calculadas con las funciones del modelo (aquí no se define ninguna variable):
- `fecha`;
- las de `mecanismos.columnas(dias)` (`notebooks/mecanismos.py`): las FUT (`fut_m_*` y `ext_g_m_cli_*`), las PAS
  (`ext_m_*` y `ext_g_m_*`) **sin compuerta**, y cada compuerta como `gate_<nombre>` (1 = encendida);
- `festivo`: `es_festivo` de `calendarios/calendario_Colombia.csv`;
- los regímenes de `indices.regimenes_diarios` (`oni`, `el_nino`, `la_nina`, `covid_fuerte`, `covid_parcial`,
  `paro_nacional_2021`, `sismo_fuerte_7d`, `desastre_activo`, `crisis_red`).

**Es para auditar y para el futuro Power BI: el modelo no lo lee.** M3s sigue leyendo sus fuentes.

**Cuidado al leerlo hacia el futuro.** Más allá del último dato real de cada fuente, las funciones del modelo rellenan
como lo haría el modelo: el clima con 0 (`fillna(0)`), el ONI repitiendo el último valor, la red y la salud pública
con 0 pasados 30 días. Esos valores son lo que el modelo vería, no datos. Dónde acaba cada fuente lo dice
`frescura.csv`. Lo único que es dato hacia adelante son los calendarios (Feria, fiestas, noches, festivos).

## Qué hacer si algo se pone en rojo

1. **Ver qué dijo el paso.** `python -m contexto --estado` da el nivel y el motivo. La salida completa está en
   `salidas/contexto/registro/<fecha>.log`: buscar `==== <hora> <paso>` y leer hasta `---- <paso>`.
2. **Correr ese paso a mano** para ver el error en la consola: `python -m contexto --solo <paso>`, o el script directo
   (la tabla de los pasos).
3. Según el caso:

| Síntoma | Qué es | Qué hacer |
|---|---|---|
| `fallo` con error de red, 404, 500, `SSLError` o tiempo límite | La fuente o la red del hospital | Nada: el paso vuelve a tocar mañana. Si se repite más de una semana, abrir la URL de la fuente en el navegador |
| `fallo` con «MenosDatos», «no se escribe para no mover el pasado» o «revisiones del pasado» | La fuente devolvió menos de lo que había, o republicó el pasado | **No forzar a ciegas.** Ver `CAPTURAS.md`, «Actualización incremental». Aceptar las revisiones (`--rehacer` o `--forzar` del script) mueve experimentos publicados y es decisión del propietario |
| `hospital` en `fallo` con error de login o de ODBC | La autenticación de Windows contra SQL Server | Comprobar que la sesión es la del usuario del dominio, que hay red del hospital y que `python -m extraccion --series` corre en una consola |
| Rojo por atraso con `sin_cambios` todos los días | La fuente dejó de publicar, o cambió de formato y el script ya no encuentra datos nuevos | Mirar la fuente. Si cambió de dirección o de columnas, se arregla el actualizador (y su documento en `calendarios/docs/`) |
| `contexto_diario` en `fallo` | Una función del modelo no corre con los archivos de hoy (un CSV con otra columna, una fecha mal escrita a mano) | El log dice el error exacto de Python. Casi siempre es una fila escrita a mano en un calendario |
| `capturas` en `fallo` pero `powerbi` y `medidas` en verde | Falló una fuente que M3s no usa (BDUA, afiliación) | No afecta al pronóstico. El detalle dice cuál; vuelve a intentarse mañana |
| Todo en amarillo por «sin corrida exitosa» | La tarea programada no está corriendo | `schtasks /Query /TN triage_contexto_diario /V /FO LIST`: mirar «Último resultado» y «Última hora de ejecución» |

**Ningún rojo detiene la operación.** El semáforo de `operacion/` lo muestra («Contexto externo»), y el pronóstico
sale con lo que haya. Lo que dice el rojo es que M3s está prediciendo con información vieja.

## La lista por confirmar

Los actualizadores estiman fechas que una persona tiene que confirmar, y las dejan en
`salidas/contexto/por_confirmar_eventos.csv` (eventos y fiestas), `por_confirmar_escolar.csv` y
`por_confirmar_desastres.csv`. La fila `por_confirmar` de la frescura avisa de lo que cae en los próximos 60 días.

**Cómo se revisa**, cuando la frescura la pone en amarillo:
1. Abrir el CSV y filtrar las filas de los próximos dos meses. Cada fila trae la regla, su acierto medido y
   `fuente_confirmar`, la última página donde salió la fecha.
2. Buscar la fecha real (la página de la alcaldía, del municipio o la prensa).
3. **Corregir el calendario a mano, no la lista:**
   - **eventos y fiestas** (`calendarios/eventos_manizales_2020_2026.csv`, `fiestas_caldas_2020_2026.csv`): poner la
     fecha real y `calidad_fecha = confirmada`. Si se canceló, `estado = cancelado`. **No borrar la fila**: la
     siguiente corrida la volvería a estimar. Las filas de tipo `fila_existente_sin_estado` necesitan que se les
     ponga `estado`, porque el modelo las ignora hasta entonces;
   - **calendario escolar**: cuando salga la resolución de la Secretaría de Educación, escribir sus filas y borrar las
     `estimada_auto` de ese año;
   - **desastres**: una detección `nueva_*` se confirma o se descarta en `calendarios/desastres_manizales_2020_2026.csv`.
     El criterio y por qué está en `ACTUALIZADORES.md`.
4. La siguiente corrida (semanal) rehace la lista.

Reglas y acierto de cada estimación: `calendarios/docs/ACTUALIZADORES.md`.

## Las tareas programadas

**No están registradas.** El orquestador deja los archivos listos; las registra el propietario a mano, con los
comandos de abajo.

| Tarea | Cuándo | Qué corre |
|---|---|---|
| `triage_contexto_diario` | todos los días, 06:30 | `wscript.exe //B //NoLogo contexto\oculto.vbs contexto\contexto.cmd` |
| `triage_operacion_semanal` | lunes, 07:00 | `wscript.exe //B //NoLogo contexto\oculto.vbs contexto\operacion_semanal.cmd` |

**Por qué cada ajuste:**

| Ajuste | Valor | Por qué |
|---|---|---|
| Cuenta | el usuario `SES\ad6708`, **solo con sesión iniciada** (`InteractiveToken`) | La extracción del hospital usa la autenticación de Windows contra SQL Server **en red**. Con S4U («ejecutar tanto si el usuario inició sesión como si no», sin contraseña) la tarea no tiene credenciales de red y la extracción fallaría. Por eso no se usa S4U, aunque `CAPTURAS.md` lo proponía |
| Ventana | ninguna: `wscript` con estilo 0 | La tarea vieja murió el 2026-10-13 porque alguien cerró su ventana negra de `cmd` (`CAPTURAS.md`, «Por qué falló la tarea»). Con `InteractiveToken` la consola aparecería en el escritorio; `oculto.vbs` la lanza oculta. Además, cada paso corre con `CREATE_NO_WINDOW` |
| Si el equipo estaba apagado | `StartWhenAvailable` | Corre en cuanto vuelve a estar disponible |
| Red | `RunOnlyIfNetworkAvailable` | El 13-10 la tarea arrancó con la red recién levantada |
| Reintentos | 3, cada 30 min | **Ojo:** el Programador reintenta cuando la tarea no pudo arrancar (o se cortó), **no** cuando el `.cmd` sale con código 1. Un paso que falla se reintenta en la corrida del día siguiente, porque sigue tocando |
| Límite | 2 h | Una corrida normal dura minutos; 2 h corta un cuelgue sin cortar una descarga lenta |
| Batería | corre con batería y no se detiene al pasar a batería | Es un portátil |
| Varias instancias | `IgnoreNew` | Si la anterior sigue corriendo, no se lanza otra. Y el orquestador tiene su propio bloqueo |
| Despertar | no (`WakeToRun = false`) | No se pidió despertar el equipo a las 06:30. Si se quiere, cambiarlo a `true` en el XML |

**El orden de las dos tareas.** La semanal corre `python -m contexto --esperar 90` antes de `python -m operacion`:
espera hasta 90 minutos a que haya terminado la corrida de hoy del orquestador. Así no lee los parquet del hospital
mientras la extracción los escribe, también cuando el equipo estuvo apagado y las dos arrancan a la vez al encenderlo.
Si se agota la espera, sigue con lo que haya. Su registro va a `salidas/operacion/registro.log`.

**Las rutas están escritas en los XML** (`C:\Users\ad6708\Documents\puebas`). Si el repositorio se mueve o cambia el
usuario, hay que editar `UserId`, `Arguments` y `WorkingDirectory` de los dos XML antes de importarlos.

### Comandos para el propietario

En una consola (`cmd` o PowerShell) **sin** permisos de administrador, con la sesión del usuario `SES\ad6708`:

```
rem 1. Registrar las dos tareas
schtasks /Create /XML "C:\Users\ad6708\Documents\puebas\contexto\triage_contexto_diario.xml" /TN triage_contexto_diario
schtasks /Create /XML "C:\Users\ad6708\Documents\puebas\contexto\triage_operacion_semanal.xml" /TN triage_operacion_semanal

rem 2. Deshabilitar la vieja: el orquestador ya incluye las capturas (paso «capturas»)
schtasks /Change /TN triage_capturas_semanales /DISABLE

rem 3. Verificar
schtasks /Query /TN triage_contexto_diario /V /FO LIST
schtasks /Query /TN triage_operacion_semanal /V /FO LIST
schtasks /Query /TN triage_capturas_semanales /FO LIST

rem 4. Probar la diaria ya (tarda unos minutos), y luego mirar su resultado
schtasks /Run /TN triage_contexto_diario
schtasks /Query /TN triage_contexto_diario /V /FO LIST | findstr /C:"Último resultado" /C:"Last Result"
type salidas\contexto\registro\tarea.log
```

**Qué tiene que salir:**
- en `/Query /V`, «Modo de inicio de sesión: Solo interactivo», «Estado: Listo» y la próxima ejecución;
- tras `/Run`, «Último resultado» **0** (o **1** si falló un paso que usa M3s: ver `--estado`; o **3** si coincidió con
  otra corrida). `267009` significa que todavía está corriendo;
- `salidas\contexto\frescura.csv` con la hora de hoy en `ultima_corrida`;
- la vieja, `Deshabilitado`.

Si `schtasks /Create` responde que el XML está mal formado, el archivo tiene que seguir en UTF-16 (como lo dejó el
orquestador): no guardarlo desde un editor que lo pase a UTF-8.

**Para quitarlas:** `schtasks /Delete /TN triage_contexto_diario /F` (y lo mismo con la semanal). Para volver a la
vieja: `schtasks /Change /TN triage_capturas_semanales /ENABLE`.

**Si `wscript` está bloqueado por política** (pasa en algunos equipos corporativos: la tarea termina al instante con
un código distinto de 0 y el log no tiene nada), la alternativa sin ventana es cambiar la acción por
`conhost.exe --headless cmd.exe /d /c "C:\Users\ad6708\Documents\puebas\contexto\contexto.cmd"`.

## Primera corrida (2026-10-15)

- `python -m contexto --todo --sin-hospital`: **143 s**. Trece pasos `sin_cambios` (las fuentes ya estaban al día por
  la fase 1), `eventos` y `fiestas` `ok` (solo por el orden de filas de la lista por confirmar, que desde entonces ya
  no cuenta como cambio), `clima_ideam` omitido (no instalado) y **`sivigila_eventos` en fallo**: la lista SharePoint
  `Microdatos` del portal del INS respondió 500. Código de salida 1.
- `python -m contexto --sin-hospital`, justo después: 17 s; se saltó los trece pasos al día y reintentó los dos sin
  corrida exitosa.
- Por `wscript` + `oculto.vbs` + `contexto.cmd`, sin consola: 19 s, código 1 (el mismo fallo); con `--solo festivos`,
  código 0; con un `.cmd` que no existe, 2. Dos corridas a la vez: la segunda sale con 3 sin correr nada.
- `python -m contexto --solo hospital`: la extracción, 16 s; el triage llega al 2026-10-15 (a medias).
- `contexto_diario.csv`: las 35 columnas de mecanismo coinciden exactamente con `mecanismos.columnas` en todo el rango.

## Límites

- **Los reintentos del Programador no ven el código 1** (ver la tabla). El reintento real es la corrida del día
  siguiente.
- **Resuelto el mismo día** (se deja constancia):
  - las columnas de red de M3s no avanzaban: `notebooks/indices.py` tenía el fin fijo en el 2026-09-20. Ahora es
    `indices.FIN_RED`, que vale el 20-sep por defecto para que los cuadernos no cambien. `contexto/diario.py` y la
    operación lo mueven al último día completo de triage;
  - `sivigila.py` y `eventos.py` escriben con `escribir_si_cambia`, así que `git status` queda limpio;
  - `eventos.py` usa el catálogo guardado cuando el portal del INS da 500 y sale con 0 y un `AVISO`
    (`calendarios/docs/VIGILANCIA.md`). Sin catálogo guardado sigue saliendo con 1.
- **El equipo tiene que estar encendido y con la sesión iniciada.** Es el precio de `InteractiveToken`. Con el equipo
  apagado, la corrida se hace al encenderlo.
- **La extracción diaria toca archivos versionados** (`salidas/triage_*.parquet` están en git): `git status` los
  mostrará modificados cada día. Es lo esperado.
- **`clima_ideam`** queda omitido hasta que exista `calendarios/clima/clima_ideam.py`; mientras tanto la fuente sale en
  rojo (no la usa M3s, así que en el semáforo de la operación cuenta como amarillo).
