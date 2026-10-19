# El pronóstico en Power BI

`prediccion.pbip` (en la raíz) es el tablero para los **jefes de urgencias**: una sola página, sin scroll, con el
volumen esperado de hoy, de los próximos 7 días, del próximo mes y por hora, y su reparto por aseguradora. Rojos =
volumen; azules = una aseguradora elegida. Lo técnico (cómo ha predicho, qué tan confiable es) se queda en el
Streamlit (`operacion/tablero.py`); ver `docs/CONTEXTO.md` «2026-10-19 (Power BI, usuario final)». **No predice
nada**: lee lo que deja `python -m operacion`.

Las medidas de la página están en la carpeta «Tablero» de `Medidas` (prefijos `T` y `V`). Cada cifra cambia a la
aseguradora elegida en el filtro o tocada en las barras.

```
python -m operacion           (o la tarea programada)  →  salidas/operacion/   (parquet anchos, 483 columnas)
python -m operacion.powerbi                            →  salidas/powerbi/     (11 CSV largos)
prediccion.pbip  →  Inicio → Actualizar                →  lee salidas/powerbi/ (parámetro CarpetaDatos)
```

## Por qué un paso intermedio en CSV y no que Power BI lea los parquet

1. **La forma.** `dias.parquet` tiene una fila por día y 483 columnas (`nueva_eps_h07_q90`, `tarde_q10`...). Power BI
   necesita tablas largas: día × jornada, día × hora, día × aseguradora... Despivotar 483 columnas en Power Query es
   frágil y lento; en pandas son veinte líneas.
2. **Qué corrida es la vigente.** El tablero elige la última corrida de cada modelo, le aplica el último ajuste por la
   red de urgencias y solo compara con C0r si es del mismo origen (`tablero._corrida` y `cargar`). Repetir esa lógica
   en M duplicaría reglas que ya viven en Python. `operacion/powerbi.py` la copia línea por línea.
3. **Sin Python dentro de Power BI.** Una consulta con script de Python obliga en el servicio a una puerta de enlace
   personal con Python instalado. Leer CSV no.
4. **CSV y no parquet**: se abren con cualquier cosa para revisarlos, y la carga fija la cultura `en-US` (punto
   decimal), así que no depende de la configuración regional del equipo.

## Qué hay en el modelo

| Tabla | De dónde | Grano |
|---|---|---|
| `Pronóstico día` | `pronostico_dia.csv` | día × modelo (principal y comparación) |
| `Pronóstico jornada` | `pronostico_jornada.csv` | día × jornada × modelo |
| `Pronóstico hora` | `pronostico_hora.csv` | día × hora × modelo |
| `Pronóstico aseguradora` | `pronostico_aseguradora.csv` | día × aseguradora × modelo |
| `Aseguradora por hora` | `pronostico_aseguradora_hora.csv` | día × aseguradora × hora (solo el principal) |
| `Red de urgencias` | `red_urgencias.csv` | día × episodio en curso |
| `Pronóstico semana` | `pronostico_semana.csv` | semana × modelo |
| `Historial`, `Historial piezas` | `historial*.csv` | día × modelo, lo predicho 15-21 días antes frente a lo real |
| `Historial aseguradora` | `historial_aseguradora.csv` | día × modelo × aseguradora: rango y real (acierto por aseguradora) |
| `Verificación hora` | `verificacion_hora.csv` | día verificado × hora: rango y llegadas reales (acierto por hora) |
| `Semáforo`, `Corrida` | `semaforo.csv`, `corrida.csv` | el estado de cada pieza y qué corrida se muestra |
| `Calendario`, `Modelo`, `Hora`, `Jornada`, `Aseguradora` | DAX | dimensiones |

Todas las medidas están en la tabla `Medidas`. Dos reglas las gobiernan:

- **`Modelo mostrado`**: sin filtro de Modelo se ve el principal (`Corrida[principal]`, hoy M3s); nunca se suman los
  dos modelos.
- **`Fecha mostrada`**: las medidas del pronóstico diario hablan siempre de **un día**: el elegido o, si no hay uno
  solo, el próximo día pronosticado. Por eso al hacer clic en un día del calendario cambian las tarjetas y gráficos de
  debajo, y sin clic muestran el de hoy. Sumar rangos del 80 % de varios días no da el rango de la suma, así que no se
  ofrece.

Las cifras se comprobaron contra los CSV con pandas el 2026-10-19 (sumas de cada tabla, error medio por modelo,
reparto por jornada y llegadas por hora): coinciden exactamente.

## Cómo se actualiza

1. Después de cada `python -m operacion` (semanal) o `--ajustar` (diario, la red), correr `python -m operacion.powerbi`.
   Hoy **no está en las tareas programadas**: se corre a mano.
2. Abrir `prediccion.pbip` y pulsar **Actualizar**.

Para llevarlo a otro equipo o a una carpeta compartida basta con cambiar el parámetro `CarpetaDatos`
(Transformar datos → Administrar parámetros).

## La página

La escribe `python -m operacion.powerbi_pagina` (con Desktop **cerrado**: rehace `prediccion.Report/definition/pages/`).
Si alguien la retoca a mano en Desktop, ese archivo deja de ser la fuente: no volver a correrlo sin comparar.

## La cadena completa y quién la sostiene (19-10)

| Paso | Qué corre | Cuándo | Dónde corre hoy | Qué necesita |
|---|---|---|---|---|
| 1. Datos | `python -m contexto` (incluye `extraccion --series`: conteos agregados de `DIM_TRIAGE`) y las fuentes externas | diario, 06:30 (`triage_contexto_diario`) | equipo del practicante, usuario `SES\ad6708`, con sesión iniciada | lectura en SQL Server con autenticación de Windows; salida a internet |
| 2. Pronóstico | `python -m operacion`: reentrena M3s y C0r, predice hasta diciembre y verifica lo pasado | lunes, 07:00 (`triage_operacion_semanal`), unos 13 min | ídem | Python 3.11 con `requirements.txt`; 16 GB de RAM, sin GPU |
| 3. Exportación | `python -m operacion.powerbi`: 13 CSV en `salidas/powerbi/` (2,4 MB) | **a mano** | ídem | nada más |
| 4. Tablero | `prediccion.pbip` lee los CSV (parámetro `CarpetaDatos`) | al pulsar Actualizar | Power BI Desktop | Power BI Desktop |

**Para que sobreviva al practicante** hacen falta:
- un equipo o servidor del hospital siempre encendido;
- una cuenta de servicio con lectura en SQL Server. Con ella las tareas pueden correr «aunque no haya sesión
  iniciada», cosa que hoy no se puede porque usan la sesión del practicante;
- añadir el paso 3 a la tarea semanal;
- un lugar compartido para el resultado del paso 3.

El tablero de urgencias del hospital lee SQL Server directamente (`Sql.Database`, en parte DirectQuery). Por eso el
camino más limpio es que el paso 3 escriba **tablas en ese mismo servidor**: el tablero las leería como lee todo lo
demás, sin carpetas ni puerta de enlace nueva. Eso exige un esquema o tablas y permiso de escritura, que no existen
hoy, y cambiar el exportador de CSV a SQL. La alternativa sin escritura en la base es dejar los CSV en SharePoint o
en una carpeta que vea la puerta de enlace.

**Integrarlo al tablero de urgencias:** como página aparte, enlazada desde el botón de triages, es lo más simple. Fundir
los modelos obliga a renombrar, porque los dos tienen una tabla `Calendario`.

## Lo que se aprendió armándolo

- **El calendario no puede depender de las tablas de hechos.** Con `CALENDAR(MIN(Historial[fecha]), ...)` y
  relaciones de esas tablas hacia `Calendario`, Desktop dio «referencia cíclica» al aplicar las consultas, aunque el
  motor las actualizaba bien una por una. Ahora va del 1-ene-2025 al 31-dic del año siguiente.
- **Desktop no siempre guarda lo que cambia una herramienta externa** (el servidor MCP de modelado): un Ctrl+S no
  escribió nada. Lo seguro es exportar el modelo a TMDL desde el MCP, cerrar Desktop sin guardar, copiar y reabrir.
- **El MCP de modelado no hace visuales.** Las páginas se escribieron como archivos PBIR
  (`prediccion.Report/definition/pages/`); se pueden retocar a mano en Desktop sin problema.

## Límites: qué se puede y qué no

**Se puede, sin el equipo de desarrollo:**
- Todo lo del tablero de Streamlit: calendario coloreado frente al día habitual, detalle del día, jornadas, horas,
  aseguradoras, aseguradora por hora, red de urgencias, semanas, historial y semáforo.
- Publicarlo en el servicio de Power BI, en un área de trabajo del hospital, **si se tiene licencia Pro** (o el área
  está en capacidad Premium/Fabric) y la institución lo autoriza. Son agregados sin dato personal: no hace falta
  seguridad por filas.

**No se puede, o necesita a TI:**
- **Actualización programada en el servicio.** El servicio no ve archivos de este equipo. Hacen falta (a) una puerta
  de enlace (*on-premises data gateway*) instalada en un equipo encendido siempre, o (b) dejar los CSV en SharePoint
  o OneDrive de la institución y leerlos desde ahí, que no necesita puerta de enlace. Las dos son decisiones de TI.
- **El modelo corre en Python, no en Power BI.** Power BI solo muestra. Si este equipo se apaga o el practicante se
  va, el tablero se queda con la última corrida (lo dice la tarjeta del encabezado y el semáforo). Para que sobreviva
  hace falta un equipo o servidor del hospital que corra las tareas programadas y deje los CSV en un sitio
  compartido. Eso es lo único que de verdad requiere al equipo de desarrollo o de infraestructura.
- **«Publicar en la web» está descartado**: hace público el informe para cualquiera con el enlace.
- **Power BI Report Server** (si el hospital usa el servidor local en vez del servicio) va por detrás de Desktop:
  hay que guardar con la versión de Desktop para Report Server, y el formato `.pbip` no se abre ahí; habría que
  guardar como `.pbix`.
- **Visuales.** No hay un calendario nativo: se arma con una matriz semana × día y color por medida. La banda del
  rango del 80 % se muestra como tres líneas (mínimo, central, máximo); la banda sombreada se puede activar a mano con
  las barras de error del gráfico de líneas. El clic sobre un día filtra la misma página; no hay un «seleccionado por
  defecto» dinámico, por eso existe `Fecha mostrada`.
- **Licencias de quien lo mira.** Con Pro, cada persona que lo abre en el servicio necesita Pro, salvo que el área esté
  en capacidad Premium/Fabric.
