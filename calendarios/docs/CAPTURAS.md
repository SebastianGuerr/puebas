# Capturas periódicas: las fuentes que no guardan su historia

**Decisión del propietario (2026-10-05).** Varias fuentes clave publican solo **el estado de hoy** y lo
sobrescriben. Lo que se sabía cada semana o cada mes existe únicamente si alguien lo guardó ese día. Para no
depender de acordarse de correr un script, la captura es **automática**: una tarea programada de Windows.

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
