# Pronóstico de solicitudes de triage — SES Hospital Universitario de Caldas

Este repositorio pronostica cuántas solicitudes de triage va a recibir urgencias por día, con su rango, su reparto por
horas y por aseguradora, y las razones que lo sostienen (calendario, contexto externo, red de urgencias). El
desenlace es siempre el **conteo total**.

| Para | Leer |
|---|---|
| El propósito del proyecto y las reglas que no se negocian | `CLAUDE.md` |
| Dónde está todo ahora | `docs/HANDOFF.md` |
| Por qué se decidió cada cosa | `docs/CONTEXTO.md` (solo crece) |
| **El trabajo que sigue, por fases** | `docs/PLAN_OPERACION.md` |
| La operación (predecir, verificar, semáforo) | `operacion/docs/OPERACION.md` |
| El contexto externo automático | `contexto/docs/CONTEXTO_EXTERNO.md` |
| Power BI | `operacion/docs/POWERBI.md` |
| Los cuadernos de análisis | `notebooks/README.md` |

---

## Correrlo en otro equipo (sin acceso a la base del hospital)

### Qué viene en el repositorio y qué no

El repositorio es **privado**. Trae los **conteos agregados** que salen de la base clínica: sin nombres, documentos,
texto clínico ni identificador de paciente. Son consultas con `GROUP BY`, y el protocolo está en
`extraccion/__init__.py`.

| Archivo | Qué es |
|---|---|
| `salidas/triage_diario.parquet`, `triage_horario.parquet` | Triages por día y por día × hora, desde 2020 |
| `salidas/triage_nivel.parquet`, `triage_edad.parquet`, `triage_estancia.parquet` | Por nivel, por banda de edad (0-4, 5-14, 15-44, 45-64, 65+) y por estancia |
| `salidas/triage_entidad.parquet` | Día × hora × aseguradora (la aseguradora es una organización) |
| `salidas/ingresos_entidad.parquet`, `entidades_clasificadas.csv` | Ingresos por entidad (la red de urgencias) y los grupos de aseguradoras |
| `calendarios/` | Festivos, clima, eventos, fiestas, sismos, seguridad y vigilancia en salud, ya procesados |
| `datos/` | Lo escrito a mano, como el registro de la red de urgencias (`eventos_red.csv`) |
| `salidas/operacion/corridas/` | Las predicciones guardadas, que son la prueba de lo que se dijo antes de que pasara |

**No vienen, a propósito:**
- la base `salidas/triage.duckdb` (texto de las notas);
- `perfil_dx_diario.parquet` (no tiene supresión de casillas pequeñas);
- `turnos_triage.parquet`;
- los microdatos crudos de SIVIGILA (5,7 GB, en `calendarios/vigilancia/crudo/`).

**Los datos de triage llegan hasta la última extracción que se subió desde el hospital.** Fuera del hospital no se
pueden actualizar: `python -m extraccion` necesita SQL Server dentro de la red.

### Instalación

Requiere Python **3.11** (medido con 3.11.9).

```
git clone https://github.com/SebastianGuerr/puebas.git
cd puebas
python -m venv .venv
.venv\Scripts\activate              (Windows)   |   source .venv/bin/activate   (Linux/Mac)
pip install -r requirements.txt
```

- `requirements.txt` trae versiones fijas y explica para qué es cada paquete.
- Con una GPU NVIDIA, instalar antes la rueda CUDA de torch (está indicado en el archivo). La operación no la
  necesita: corre en CPU.
- `pyodbc` se instala igual fuera del hospital, pero no se usa.

Comprobar la instalación:

```
python -m pytest NLP/tests -q
python -m operacion --estado          # verifica las corridas guardadas y calcula el semáforo; no entrena
```

### Qué se puede hacer fuera del hospital

| Sí | Cómo |
|---|---|
| Predecir con los datos que trae el repositorio | `python -m operacion` (**sin** `--extraer`). Si ya existe la corrida de ese origen, no la rehace |
| Ver el tablero | `streamlit run operacion/tablero.py` |
| Exportar para Power BI | `python -m operacion.powerbi` → `salidas/powerbi/` |
| Poner al día las fuentes externas libres | `python -m contexto --sin-hospital --solo festivos sismos desastres enso eventos fiestas mindefensa`. Sin `--solo`, la primera vez corre **todo**, incluidas las descargas grandes de SIVIGILA (hasta 40 min por paso) |
| Abrir y ejecutar los cuadernos | `notebooks/` |
| Desarrollar las fases de `docs/PLAN_OPERACION.md` | Todas, salvo lo que pida dato nuevo del hospital |

| No | Por qué |
|---|---|
| `python -m extraccion`, `python -m operacion --extraer`, el paso `hospital` de `contexto` | Necesitan SQL Server (DWSES) con autenticación de Windows, dentro de la red del hospital |
| `python -m NLP.procesar`, `embedding/` | Necesitan `salidas/triage.duckdb` y Ollama; no forman parte de la operación |

### Cómo viajan los datos y el código

- **Los datos van del hospital a casa.** En el hospital: la extracción, commit de `salidas/*.parquet` y push.
- **El código va de casa al hospital.** En casa: se desarrolla, commit y push. En el hospital: pull y se corre con los
  datos del día.
- Antes de hacer pull en el hospital, conviene hacer commit de la extracción del día, porque la tarea diaria modifica
  `salidas/triage_*.parquet`. En casa esos archivos **no se modifican**; así nunca chocan.
