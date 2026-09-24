# Handoff — dónde está todo ahora

**Este archivo se reescribe.** Describe el presente, no la historia. La historia —qué se
decidió, cuándo y por qué— está en `docs/CONTEXTO.md` y esa solo crece.

Regla 10 de `CLAUDE.md`. Se actualiza **durante** la sesión, cada vez que algo cambia de
estado: una sesión que se corta a la mitad tiene que dejar esto utilizable igual.

**Última actualización: 2026-09-24.**

---

## En una frase

Se está en **exploración**, no en modelado. El objetivo de esta etapa es saber qué variables
existen, cómo se comportan y qué relaciones reales hay entre las tablas y los calendarios.
**Nada de predicción hasta terminarla.**

---

## Lo más nuevo, y lo que más cambia el plan

**1. La vía pediátrica pasa a ser el camino principal.** Las bandas 0-4 y 5-14 tienen
**72,5 % y 43,5 % de amplitud estacional** contra 5-8 % de las adultas, con pico en mayo y
valle en enero. Es la firma de una temporada respiratoria, y prueba la hipótesis central
**con 6,7 años y sin depender del NLP**. `salidas/triage_edad.parquet`, 100 % de cobertura.

**2. El clima unificado está ARREGLADO (2026-09-23).** Tenía seis errores, no uno; el peor
fabricaba tormentas cada vez que el pluviómetro dejaba de reportar (+20,05 mm/día falsos,
ahora −0,36). Ya se puede cruzar contra clima. **Límite: solo el 42,9 % de los días tiene
pluviómetro** — para transiciones día a día, `precip_con_estacion` o acumulados de 7 días.
Ver `calendarios/docs/CLIMA.md`.

**3. El nivel de triage mide la decisión del hospital, no la gravedad del paciente.**
Corrección del propietario. Todos los registros son demanda real. De ahí la distinción que
ahora organiza todo: **conteo, edad y hora miden a la población; nivel y estancia miden a la
institución.** Para comparar años, solo los primeros.

**4. Aquí no hace calor, nunca.** 0 días con máxima > 26 °C en 2.432. Descarta la vía
vectorial local y deja la respiratoria, que es la hipótesis original.

---

## EN CURSO: seguir el trabajo desde el equipo de casa (RTX 4060, 8 GB)

**Qué quiere el propietario:** clonar este repositorio en su equipo de casa y seguir desde
allí; que la GPU procese de noche las ~95.000 notas y pruebe prompts y modelos, y traer los
resultados de vuelta. El porqué y lo descartado: `docs/CONTEXTO.md`, 2026-09-24.

**Hecho y certificado (2026-09-24):**
- `NLP/salidas/tabla/notas_triage.csv.gz` — 95.424 notas, 2025-01-08 a 2026-09-24 (el último
  día incompleto: descartarlo al analizar). Seis columnas: `id, fecha, nivel, nivel_nombre,
  edad_banda, nota`. Lo identificable **borrado**. Auditoría: **0 fallos**. Su certificado
  (conteos y sha256 del CSV) es `auditoria.json`, al lado. Se rehace con
  `python -m NLP.nube.tabla --exportar --forzar` (solo aquí: necesita la base).
- `mapa_local.parquet` (`id → OID`) **se queda aquí**. Es lo único que devuelve una fila a su
  triage. Hay dos mapas apartados en la misma carpeta, de una muestra y de una corrida
  fallida: sus CSV nunca salieron, se pueden borrar.
- `requirements.txt` rehecho; `calendarios/clima_unificado.csv.gz` (antes `.csv`).
- Retirados del índice: `triage_limpio_antiguo.csv` y `exploracion.ipynb` (texto real).

**BLOQUEANTE antes de clonar:** el **historial** del repositorio en GitHub tiene notas crudas
con OID (ver CONTEXTO, 2026-09-24). Un clon las copia. Decisión #6 abajo.

**Falta para que el clon sirva:**
1. **Sacar de `.gitignore` el CSV y las series**, que el sistema de permisos le bloqueó a
   Claude. Si el propietario lo aprueba, estas líneas van en «Lo que SI se versiona» (y
   `NLP/salidas/` y `salidas/` pasan a `NLP/salidas/*` y `/salidas/*`, porque git no
   re-incluye un archivo de una carpeta ignorada entera):
   ```
   !NLP/salidas/tabla/
   NLP/salidas/tabla/*
   !NLP/salidas/tabla/notas_triage.csv.gz
   !NLP/salidas/tabla/auditoria.json
   !/salidas/triage_diario.parquet
   !/salidas/triage_horario.parquet
   !/salidas/triage_nivel.parquet
   !/salidas/triage_edad.parquet
   !/salidas/triage_estancia.parquet
   ```
   El bloque «NUNCA» del final sigue ganando sobre el mapa y las DuckDB.
2. **El código de casa no existe:** leer el CSV, armar el prompt con la versión que se elija
   de `NLP/prompts/`, llamar a Ollama en la GPU, guardar cada resultado con `id`,
   `version_prompt` y `modelo`. Y aquí, el camino de vuelta: resultado → `id` → mapa → OID.
3. **Pasar el arreglo de las fechas con guion a `enmascarar.py`** (hoy solo lo tiene la
   tabla, `_red_de_fechas`): el paquete de la nube tiene el mismo hueco.
4. En el equipo de casa: `pip install -r requirements.txt` con `torch` CUDA (ver el
   comentario en el archivo), y Ollama con el modelo. Allí la regla 6 («No hay GPU») no
   aplica.

---

## EN CURSO: fase de CPU cerrada; la red de seguridad está construida

**Decisión del propietario (2026-09-24): no se itera más el prompt en la CPU.** Lo que la CPU
podía enseñar ya está medido. Candidatos listos en `NLP/prompts/v1_7.py` (8B) y
`NLP/prompts/v1_7_14b.py` (14B, abstención suavizada); **producción (`NLP/prompt.py`, v1.6)
intacta**. La corrida de producción está **parada**.

**Qué se sabe del modelo** (detalle en `docs/CONTEXTO.md`, entradas del 2026-09-24):
- **El 8B llegó a su techo**: ~9-10/17 fallos de la sonda arreglados, leídos a mano.
- **El 14B es mejor en fidelidad** (duelo 5-2, sonda leída 11/17) pero **no es viable en
  CPU**: 9,3 GB, ~8 min de carga, 20-120 s/nota. En GPU sí.
- **El riesgo que queda son los descartes falsos**, y son **inestables** (la misma nota sale
  bien o descartada según la corrida). No se arreglan con prompt.
- **No hay acumulación de contexto**: cada llamada es independiente; la tasa de fallo es
  plana por orden de procesamiento. La inestabilidad en una nota es señal de que adivina.

**La red de seguridad, construida el 2026-09-24** (`NLP/cadena.py`): toda salida «sin motivo
clinico» cuya nota trae evidencia clínica se repite con `construir_segunda_pasada()`, un
prompt que no admite abstenerse. Si vuelve a descartar o inventa, queda «sin motivo clinico»
**marcada `revisar`**. Integrada en `banco.py` (la sonda marca `<segunda>` / `<revisar>`) y
en `NLP/nube/` como dos viajes (`--exportar --segunda-pasada`; los pendientes **no** se
fusionan con la base). Documentada en `NLP/docs/EVALUACION.md` y `NLP/docs/NUBE.md`.
283 pruebas en verde.

**Medición real de la red**: sonda de 32 notas con qwen3:8b + v1.7 + cadena completa,
**corriendo el 2026-09-24** (salida en el scratchpad de la sesión, `sonda_cadena_8b.txt`).
Si se perdió: `python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py`, **nada más en
paralelo**.

```
python -m NLP.banco --oid <OID> --prompt NLP/prompts/v1_7.py               una nota
python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py                   la sonda (32 notas)
python -m NLP.banco --sonda --prompt ... --sin-filtros                     el modelo solo
python -m NLP.duelo --modelos qwen3:8b qwen3:14b --oids ...                mismo prompt, sin filtros
```

**Filtros de `posprocesar()`**, en este orden, todos con pruebas: `es_tramite_puro` →
`quitar_lado_inventado` → `quitar_parte_inventada` → `quitar_embarazo_inventado` →
`restaurar_antier` (también «el día anterior») → `quitar_identificadores`. Solo quitan,
salvo `restaurar_antier`, que devuelve la palabra exacta de la nota.

**Límite duro de esta máquina**: 15,9 GB de RAM. Correr modelo + agentes en paralelo **colgó
la terminal** el 2026-09-23. Una sola cosa pesada a la vez.

---

## Antes de contratar GPU

Recomendada: **RTX PRO 6000 (96 GB) a ~2.088 COP/h** — 33 COP/h más que la 5090 con el triple
de memoria. Costo estimado de todo: decenas de miles de pesos; el piloto de 30 min da la cifra
real antes de comprometerse.

- [x] **Capa de seguridad `NLP/nube/`** (2026-09-23): sale solo `id` aleatorio + prompt con la
      nota enmascarada; OID, fechas y mapa quedan en local; paquete barajado; auditoría que
      falla cerrado. Auditada de forma independiente sobre 300 notas reales: 0 restos, orden
      vs OID +0,049, 323→323 términos clínicos. Ver `NLP/docs/NUBE.md`.
- [x] **Comprobación de fidelidad automática**: 13 detectores fuertes en `fidelidad.py`,
      cada uno validado leyendo lo que marca.
- [x] **Fase de CPU cerrada** (2026-09-24): el 8B llegó a su techo; el 14B es mejor pero
      solo en GPU. El modelo final se decide en la GPU, con la sonda.
- [x] **Red de seguridad contra descartes falsos** (`NLP/cadena.py`), local y nube.
- [ ] **Cuatro entradas de glosario** que son trabajo del propietario: «no me baja el azúcar»,
      «oídos tapados», «congestionado», «hipo».
- [ ] **Banco completo** con el candidato final (~420 llamadas).
- [ ] **Promover a producción**: `NLP/prompt.py` + `procesar.py` llamando a
      `cadena.procesar_nota` + columnas `version_prompt`, `modelo` y `pasada` en
      `nota_triage`. **Sin la columna `pasada`, al fusionar un `revisar` se vuelve un
      descarte normal**: hoy la única marca es `NLP/salidas/nube/revisar.txt`.
- [ ] **Probar que el enmascarado no cambia la salida**: mismas notas enmascaradas y sin
      enmascarar, mismo modelo.
- [ ] **Decisión institucional** sobre procesar datos de salud en infraestructura de un
      tercero. La capa técnica reduce el riesgo; la autorización no la da el código.
- [ ] En la GPU: competencia de 2-3 modelos (el agente de investigación recomienda
      `gemma4:26b` o `gemma4:31b`, `qwen3:32b` como control, y el 8B de referencia) con la
      sonda y el banco, antes de la corrida completa.

---

## Lo que cambió hoy y hay que saber antes de nada

**La regla 1 estaba mal escrita.** No es «no tocar la base», es «no exponer dato personal».
La base **sí** se explora: esquema primero, clasificar columnas, y solo agregados de las no
sensibles. El protocolo está en `extraccion/__init__.py`. Eso desbloqueó todo lo de abajo en
una sola sesión.

**Se encontraron dos derivas de medición no documentadas**, y eso convierte la auditoría en
un paso obligatorio:

1. **El criterio de triage derivó desde enero de 2025.** La caída del 23,9 % del volumen es
   en buena parte reclasificación: «no urgente» −57,4 %, «diferido» +101,5 %.
2. **La estancia tiene tres regímenes de registro** (saltos en 2021-08 y 2026-07). Solo vale
   el régimen 2: agosto 2021 a junio 2026.

**Antes de usar cualquier columna nueva: mirar su serie mensual buscando escalones.**

---

## Qué está corriendo

**La corrida de producción (`NLP.procesar`) está parada** desde el 2026-09-23. Quedó en
~3.087 notas, todas de enero de 2025, **procesadas con v1.6**: habrá que rehacerlas con la
versión final. Al relanzar, hacerlo con la cola **por hash del OID** (hoy procesa en orden
cronológico, `procesar.py:223`, `disperso=False`).

---

## Qué existe y se puede usar hoy

| Archivo | Qué es | Cobertura |
|---|---|---|
| `salidas/triage_diario.parquet` | 2.454 días | 2020-2026 |
| `salidas/triage_horario.parquet` | 55.844 casillas día×hora | 2020-2026 |
| `salidas/triage_nivel.parquet` | 177.864 filas día×hora×nivel | **100 %** desde 2020 |
| `salidas/triage_edad.parquet` | 12.339 filas día×banda | **100 %** desde 2020 |
| `salidas/triage_estancia.parquet` | 2.455 días | 91,1 %, **solo vale régimen 2** |
| `salidas/triage.duckdb` | `nota_triage` + `embedding` | 1,5 % del corpus |
| `NLP/salidas/tabla/notas_triage.csv.gz` | 95.424 notas sin identidad, auditadas | 2025-01-08 a 2026-09-24 |
| `calendarios/clima_unificado.csv.gz` | clima diario unificado (antes `.csv`) | 2020-01-01 a 2026-08-28 |

Los cuatro parquet se regeneran con `python -m extraccion --series`. **Los cuadernos leen de
ahí y no de SQL Server**, que es lo que permite que otra persona reproduzca las figuras.

---

## Lo construido, y cómo se corre

```
python -m extraccion --esquema            columnas y su clasificación. No baja datos
python -m extraccion --cobertura          qué está lleno y desde cuándo
python -m extraccion --series             escribe salidas/*.parquet

python -m clustering.visualizaciones      7 figuras sobre la serie total
python -m clustering.visualizaciones.pruebas    5/5

notebooks/01_la_serie_de_triage.ipynb     25 celdas, 6 figuras, 0 errores
notebooks/02_el_hospital.ipynb            20 celdas, 2 figuras, 0 errores
```

**`clustering/visualizaciones/`** — 994 líneas en 6 archivos, 3 con cálculo. La regla que
lleva dentro: nunca se dibuja el conteo crudo de una categoría, siempre el índice de
especialización, y las casillas con esperado < 5 se tapan en gris.

**`extraccion/`** — 2 archivos. El único módulo que habla con SQL Server. Todas las
consultas llevan `GROUP BY`.

**`notebooks/01_la_serie_de_triage.ipynb`** — ejecutado, 0 errores. Cubre: el volumen y su
caída, el ritmo horario, qué tipo de hospital es, la reclasificación y los regímenes de la
estancia. Cada figura con su lectura y sus límites.

---

## Hallazgos que condicionan lo que venga

1. **La serie no crece: −23,9 % desde el pico de 2024** — y buena parte es reclasificación.
2. **2020 es un cráter de COVID** (−64 % enero→abril). No entra en entrenamiento sin tratarlo aparte.
3. **La hora manda: 13,9× contra 1,57 ×** del día de la semana.
4. **El día tiene dos jorobas** → harán falta 2-3 armónicos de 24 h, no uno.
5. **Hay interacción hora × día**: la madrugada pesa 1,62× más el domingo que el jueves.
6. **51,4 % del hospital es no urgente; las emergencias son el 0,4 %.** Sostiene el
   mecanismo de la incapacidad que el proyecto quiere medir.
7. **12,6 % es obstétrico** (niveles `-G`). Población aparte, conviene separarla.
8. **`GENDIAGNO1` está vacío (0,6 %)**: no hay CIE-10 gratis. No volver a buscarlo.
9. **La ventana con texto (2025-2026) es justo la ventana contaminada** por la deriva.

---

## Esperando decisión del propietario

| # | Qué | Por qué importa |
|---|---|---|
| 1 | **¿Qué pasó en enero y en noviembre de 2025?** ¿Directriz, contrato, auditoría? | Es la única explicación de la deriva que no está en la base |
| 2 | **¿Qué significa `HCCFECSAL`** en cada régimen? | Sin eso la estancia no se interpreta ni dentro del régimen 2 |
| 3 | **La lista de 6-8 categorías clínicas** | Bloquea el banco etiquetado, y el banco bloquea la comparación de métodos |
| 4 | **Reordenar la cola del NLP por hash del OID** (parar y relanzar la corrida) | Muestra uniforme de 20 meses en ~5 días en vez de 70 días en orden cronológico |
| 6 | **Limpiar el historial de git**: repo nuevo con un commit limpio (recomendado) o `git filter-repo` + `push --force` | Hoy un clon copia 6.501 notas crudas con OID y otros bancos de notas. Irreversible: lo decide el propietario |
| 7 | **Autorizar que el CSV de notas y las series salgan de `.gitignore`** (líneas arriba, en «EN CURSO: equipo de casa») | Sin eso el clon no trae los datos. El sistema de permisos se lo bloqueó a Claude |
| 5 | **Permitir una primera pasada léxica en SQL** sobre `HCTMOTCON`: `CASE WHEN ... LIKE` + `GROUP BY` día; el texto nunca sale del servidor | Calendario de motivos de los 20 meses **hoy**, y es además el «piso léxico» del banco de comparación |

---

## Pendiente de hacer, en orden

1. ~~Arreglar el clima unificado~~ — **hecho el 2026-09-23.**
2. **Cuaderno 03: la estacionalidad pediátrica año a año.** ¿Se repite, o la fabrica el
   promedio de siete años? Y separar lluvia de calendario escolar, que hoy están confundidos.
3. **Cuaderno 04: el ciclo horario con Fourier.** Periodograma y cuántos armónicos hacen falta.
4. **Añadir `nivel_triage` a `nota_triage`** y que `NLP/` lo extraiga, como hace con la
   fecha. **No tocar mientras la corrida esté viva.**
5. **Auditar `HCAREA`** de `HCNCONCOTRI_DW` — posible categoría estructural gratis desde 2020.
   Mirar su serie mensual buscando escalones antes de usarla.
6. **Reescribir `clustering/`** contra la base: retirar `fechas.py`, las anclas posicionales
   y las salidas sueltas.
7. **Borrar los archivos muertos** — lista aprobada, ejecución pendiente. Todos están en git.

---

## Trampas conocidas

- **DuckDB admite un solo escritor y bloquea a los lectores.** Leer de `triage_vista.duckdb`.
- **`calplot` no está instalado**; el calendario está reimplementado en `figuras.py`.
- **Las salidas de `clustering/salidas/` y `patrones/salidas/` están muertas** (bge-m3,
  corpus de 9.256 notas que ya no existe). No citar esos números.
- **El supuesto del lift no está medido**: se asume que la cobertura de `HCTMOTCON` no
  depende de la categoría.
- **`ipykernel`, `nbformat` y `nbconvert`** ya están en `requirements.txt` (2026-09-24), con
  `hdbscan`, `umap-learn` y `pytest`, que también se usaban sin estar.
- **`ollama pull` puede fallar por DNS** contra `r2.cloudflarestorage.com` en la red local; al
  reintentar funcionó. Alternativa: `ollama pull hf.co/usuario/repo:Q4_K_M` (Hugging Face).
- **`CLAUDE.md` todavía dice «No hay GPU» (regla 6) y «33 pruebas en verde»**: los dos quedaron
  viejos (hoy son 283 pruebas). Se actualizan al cerrar la sesión.
- **La segunda pasada en la nube va a otro archivo de respuestas** (`correr_en_gpu.py
  --salida respuestas_segunda.jsonl`): el mapa del 2º paquete reemplaza al del 1º.
