# Runbook de operación

Ítem E1.4 del plan (`PLAN.md` §8). Instrucciones para instalar, ejecutar y
diagnosticar el pipeline de `NLP/` sin necesidad de leer el código. Todos los
comandos se ejecutan **desde la raíz del repositorio**
(`C:\Users\ad6708\Documents\puebas`) con el intérprete del proyecto:

```
C:\Users\ad6708\Documents\puebas\.venv\Scripts\python.exe -m NLP.<paquete>.<modulo>
```

Este documento usa `python` como atajo de esa ruta completa. Las salidas de
consola con tildes pueden verse mal en `cmd.exe` (códigos de página cp1252); usar
PowerShell o fijar `PYTHONIOENCODING=utf-8` si aparecen caracteres corruptos.

## 1. Instalación desde cero

| Paso | Comando | Qué verifica |
|---|---|---|
| 1. Python 3.11 | `python --version` debe dar `3.11.x` (verificado el 2026-09-16: `Python 3.11.9`) | la versión que fija `requirements.txt` |
| 2. Entorno virtual | `python -m venv .venv` en la raíz del repositorio | aísla las dependencias del proyecto |
| 3. Activar | PowerShell: `.venv\Scripts\Activate.ps1` | — |
| 4. Dependencias | `.venv\Scripts\python.exe -m pip install -r requirements.txt` | instala pandas, spaCy, symspellpy, language-tool-python, torch, transformers, etc. (ver `requirements.txt` para la lista fijada y las exclusiones justificadas) |
| 5. Modelo de spaCy | `python -m spacy download es_core_news_md` | exigido por `requisitos.py`; sin él la fase 2 corrige sin vocabulario ni protección de nombres propios |
| 6. Java (para LanguageTool) | comprobar con `java -version`; se necesita un JRE/JDK instalado aparte (no lo instala `pip`) | verificado el 2026-09-16: `java version "21.0.12.1"`. `language_tool_python` descarga el paquete de LanguageTool la primera vez que se instancia (necesita red la primera vez) |
| 7. Ollama (opcional, fase 5b) | instalar desde ollama.com; luego `ollama pull qwen2.5:3b-instruct` | verificado el 2026-09-16: `ollama version is 0.34.1`. Sin él, `extractor.disponible()` da `False` y la fase 5 sigue solo por reglas — no detiene la corrida |
| 8. Conexión a la base de datos | credenciales integradas contra `ls-cobra` / `DWSES` (`nucleo/conexion_bd.py`) | necesaria para una corrida nueva (`procesar.py`) y para las frecuencias de una reparación; **no** para reparar con `--csv` de respaldo, ni para `requisitos.py`, ni para `paridad_docs.py` |

Tras instalar, verificar con:

```
python -m NLP.nucleo.requisitos
```

Salida esperada (verificada el 2026-09-16, con todos los artefactos ya
construidos):

```
REQUISITOS DEL PIPELINE

  [OK ] exigido   lexico_clinico
  [OK ] opcional  lexico_casing
  [OK ] opcional  clasificador_frases
  [OK ] exigido   lexico_externo
  [OK ] exigido   catalogo_sintomas
  [OK ] exigido   diccionario_siglas
  [OK ] exigido   es_core_news_md

Todo en su sitio.
```

Si falta alguno, este mismo comando imprime, para cada exigido, qué se rompe y el
comando que lo arregla — **con una excepción documentada en la sección 5**: la
receta que imprime para `clasificador_frases` es peligrosa, no seguirla al pie de
la letra.

## 2. Artefactos: tabla completa

Fuente: `NLP/nucleo/requisitos.py` (tabla `ARTEFACTOS`) y `ESTADO.md` §2. "Exigido"
significa que, sin él, la corrida termina completa y con datos equivocados
(`requisitos.exigir()` la detiene primero); "opcional", que su ausencia deja una
señal visible.

| Artefacto | Tipo | Comando que lo regenera | Qué se rompe si falta |
|---|---|---|---|
| `datos/diccionario_siglas.json` | exigido, versionado | viene con el repo (`NLP/datos/`); se edita a mano | no se expande ninguna sigla |
| `embedding/datos/catalogo_sintomas.json` | exigido, versionado | viene con el repo (`embedding/datos/`) | la depuración no reconoce ningún síntoma |
| `datos/lexico_externo.txt` | exigido, generado | `python -m NLP.recursos.extraer_cie10` | el léxico clínico se queda sin el vocabulario del CIE-10 |
| `salidas/lexico_clinico.json` | exigido, generado | `python -m NLP.recursos.lexico` | la fase 5 descarta toda oración larga: se pierde el motivo de consulta (medido: 25,1 % de notas pierden contenido, 18,1 % pierden más de la mitad — `decisiones/2026-09-15-artefactos-y-version-corrector.md`) |
| modelo spaCy `es_core_news_md` | exigido, externo | `python -m spacy download es_core_news_md` | la fase 2 corrige sin vocabulario ni protección de nombres propios |
| `salidas/lexico_casing.json` | opcional, generado | `python -m NLP.recursos.casing` (requiere BD) | no se restaura ninguna sigla a mayúscula |
| `salidas/clasificador_frases.joblib` | opcional, generado | `from NLP.reduccion import frases; frases.entrenar()` — **NUNCA** `python -m NLP.reduccion.frases` (sección 5) | la fase 5 pierde la capa que cubre trámite no enumerado por los patrones |

Artefactos adicionales que no comprueba `requisitos.py` pero que la corrida
necesita o usa (`ESTADO.md` §2 y observación directa, sección 6 de este
documento):

| Artefacto/servicio | Comando | Si falta |
|---|---|---|
| Servidor LanguageTool (Java) | se levanta solo al llamar `ortografia.iniciar_languagetool()` | si Java no está instalado, `iniciar_languagetool()` puede fallar sin capturarse (ver sección 6); si el servidor arranca pero una consulta puntual falla, `corregir()` lo captura y sigue sin esa corrección |
| `datos/diccionario_coloquial.json` | viene con el repo; se edita a mano | la fase 3 no expande coloquialismos (si falta el archivo, `normalizacion.cargar()` lanza excepción al leerlo) |
| `salidas/cache_correcciones.json` | se llena solo, procesando | sin ella cada corrida repite toda la fase 2 desde cero (más lenta, no incorrecta) |

## 3. Comandos por escenario

### 3.1 Corrida nueva (desde la base de datos)

```
python -m NLP.nucleo.requisitos
python -m NLP.procesar
```

Qué mirar: la primera línea imprime `Registros a procesar: N | LLM: si/no`. Si
`N` es menor que lo esperado, revisar `LIMITE_REGISTROS` en `procesar.py:70`
o pasar `--limite`. El progreso se imprime bloque a bloque
(`BLOQUE_ESCRITURA = 250`, `procesar.py:93`); el CSV se puede abrir mientras
corre. Al final: "Correcciones sospechosas de estropear la nota" (revisar antes
de dar la corrida por buena), "Correcciones frenadas por el guardián clínico"
(qué reglas de protección actuaron), "Palabras dejadas intactas por falta de
evidencia" (candidatas a entrar en el diccionario), y el resumen de notas
señaladas por `motivo_descarte`.

Opciones: `--limite N` (procesa N notas nuevas, no relee las ya hechas);
`--sin-llm` (desactiva el extractor de Ollama en la fase 5); `--rehacer` (aparta
el CSV existente con `rotar()` y procesa todo desde cero — perder esto significa
perder el progreso incremental, usar con intención).

### 3.2 Reanudar una corrida interrumpida

No hace falta ninguna opción especial: `python -m NLP.procesar` **continúa** el
CSV existente por diseño (`procesar.py:568-580`, comentario "Relanzar CONTINUA el
CSV; no lo rehace"). Lee los `OID` ya escritos en `triage_limpio.csv` y la
consulta a la base de datos los excluye. La caché de correcciones
(`cache_correcciones.json`) conserva lo ya corregido, así que reanudar es barato.

### 3.3 Reparar un CSV existente sin sustituirlo

```
python -m NLP.reparacion.reparar --limite 200      # prueba sobre 200 notas
python -m NLP.reparacion.reparar                   # sobre todo el CSV, sin tocar nada
```

Por defecto **no modifica** `triage_limpio.csv`: escribe `triage_reparado.csv` e
`informe_reparacion.csv` en `salidas/`. Qué mirar: al final, el resumen por
categoría (`intacta`, `ortografia`, `recupero_motivo`, `perdio_motivo`,
`normalizacion`) y, si hay `perdio_motivo`, la tabla de términos perdidos por
frecuencia — **no aplicar la reparación mientras haya alguno con veredicto
real** (criterio de E0.2, `PLAN.md` §8).

Opciones: `--con-llm` (usa el extractor de Ollama en la fase 5, más lento);
`--csv <ruta>` (repara un CSV distinto al de `salidas/`); `--salida-dir <carpeta>`
(escribe el reparado y el informe en otra carpeta, para no pisar una reparación
en curso — **usar esto si hay un job de reparación corriendo en segundo plano**,
nunca apuntar dos reparaciones al mismo `salidas/`).

### 3.4 Revisar el informe de reparación

```
python -m NLP.reparacion.revision
python -m NLP.reparacion.revision --termino cefalea
```

Sin argumentos: recuento por categoría, veredicto `recupero > perdio: CUMPLE /
NO CUMPLE`, y la lista **completa** (no solo los 25 más frecuentes que imprime
`reparar.py`) de términos perdidos por frecuencia, con cuántas veces cada uno se
recupera en otras notas. Con `--termino <palabra>`: las notas concretas donde se
pierde ese término, con 60 caracteres de contexto antes y después — es la forma
de decidir si una pérdida es benigna (administrativa) o real.

### 3.5 Aplicar la reparación

```
python -m NLP.reparacion.reparar --aplicar
```

Repite todo el proceso de 3.3 y, si `empeoraron == 0` (ninguna nota en
`perdio_motivo`), sustituye `triage_limpio.csv` apartando la versión anterior con
`nucleo/salida.rotar()` (conserva 3 versiones con fecha). Si hay alguna nota que
pierde terminología, el comando se niega a aplicar y termina con código de salida
1 — corregir la causa antes de repetir con `--aplicar`.

### 3.6 Revectorizar tras un cambio de texto

```
python -m embedding.vectorizar
```

Verificado el 2026-09-16 (`--help`, sin argumentos adicionales que requieran
red ni BD): usa `--csv`, `--limite`, `--bloque` (2000 por defecto), `--rehacer`.
`embedding/` deduplica por `sha1(texto)[:16]`, no por `OID` (`PLAN.md` §7): un
texto reparado se revectoriza solo, sin necesitar `--rehacer`; los vectores del
texto antiguo quedan huérfanos en `vectores.f32` (ocupan disco, no rompen nada).

**Aviso**: `python -m embedding.estructurar` (fase 4 de `embedding/`, extracción
estructurada) está roto hoy — ver el error conocido en la sección 6, punto 1. No
usarlo hasta que se corrija `embedding/extraccion.py`.

### 3.7 Validar el agrupamiento

```
python -m clustering --validar
```

No se ejecutó en la preparación de este documento por ser una prueba costosa
(recalcula reducciones para varias pruebas: modelo nulo, estabilidad, siluetas,
codo de temas, catálogo clínico — el propio `--help` de `clustering` lo describe
así). Ejecutar tras cualquier cambio que altere la longitud o el contenido de
`texto_embedding`; comparar contra la referencia de `PLAN.md` §7 (p99 de 95
tokens, máximo 170, 10 de 5.020 textos truncados con `bge-m3` a 128 tokens) para
detectar más truncaciones que antes.

### 3.8 Correr las pruebas

```
python -m pytest NLP/tests -q
```

Verificado el 2026-09-16: `NLP/tests/` existe pero solo contiene una carpeta
`datos/` vacía, sin ningún archivo `test_*.py`. Salida real:

```
no tests ran in 0.07s
```

E2.1 (`PLAN.md` §8) todavía no se ha ejecutado: no hay ninguna prueba automatizada
sobre el pipeline.

### 3.9 Comprobar paridad de la documentación

```
python -m NLP.evaluacion.paridad_docs
python -m NLP.evaluacion.paridad_docs --estricto
```

Recorre `NLP/**/*.py` y las fichas de `ARQUITECTURA.md` §2. Salida real,
2026-09-16:

```
Paquete:   C:\Users\ad6708\Documents\puebas\NLP
           42 archivos .py exigen ficha; 10 __init__.py solo con docstring, exentos
Documento: C:\Users\ad6708\Documents\puebas\NLP\docs\ARQUITECTURA.md
           41 fichas reconocidas en §2

Faltantes (archivo sin ficha): 1
  - evaluacion/perturbar.py
Huérfanas (ficha sin archivo): 0
Documentos de docs/ sin sección '## Historial': 1
  - README.md

Resultado: 1 faltantes, 0 huérfanas, 1 documentos sin Historial
```

`--estricto` devuelve código de salida distinto de cero si hay algo pendiente
(útil para CI); forma parte del gate de todas las etapas (`PLAN.md` §4.2). Nota:
este documento (E1.3/E1.4) corrige el punto de `README.md` sin `Historial`; el
faltante de `evaluacion/perturbar.py` queda pendiente porque `ARQUITECTURA.md` no
está entre los archivos que este ítem puede tocar.

### 3.10 Procedimiento completo: limpiar el CSV actual y regenerar los embeddings

Deja `triage_limpio.csv` con el corrector vigente y los vectores al día. Se ejecuta entero
y en este orden desde la raíz del repositorio. `PY` es `.venv\Scripts\python.exe`.

```
REM 1. Comprobar que estan los artefactos que el proceso da por hechos
%PY% -m NLP.nucleo.requisitos

REM 2. Frecuencias del corpus completo (si no existen o son de otra corrida)
%PY% -m NLP.recursos.corpus_lexico

REM 3. Lexico clinico, con los gazetteers integrados
%PY% -m NLP.recursos.lexico

REM 4. Si VERSION_CORRECTOR cambio, migrar la cache en vez de tirarla
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva>
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva> --aplicar

REM 5. Reparar sin tocar nada, y revisar el informe termino a termino
%PY% -m NLP.reparacion.reparar
%PY% -m NLP.reparacion.revision

REM 6. Medir el resultado contra el CSV vigente ANTES de sustituirlo
%PY% -m NLP.evaluacion.calidad --csv NLP\salidas\triage_limpio.csv --comparar NLP\salidas\triage_reparado.csv

REM 7. Solo si los numeros mejoran: aplicar
%PY% -m NLP.reparacion.reparar --aplicar

REM 8. Revectorizar y validar
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

El paso 6 es el que decide: `--comparar` cruza por `OID` y muestra la diferencia columna a
columna. Lo que tiene que subir es la retención de terminología; lo que tiene que bajar es
el número de notas que se quedan sin terminología clínica.

El paso 7 no sustituye nada si quedan notas en `perdio_motivo` sin revisar: `reparar.py` se
niega y sale con código 1. La versión anterior del CSV la aparta `salida.rotar()`.

### 3.11 Generar notas nuevas desde la base de datos

```
REM Corrida normal: procesa las notas que aun no estan en el CSV
%PY% -m NLP.procesar

REM Prueba corta antes de una corrida larga
%PY% -m NLP.procesar --limite 200

REM Rehacer el CSV entero desde cero (aparta el anterior)
%PY% -m NLP.procesar --rehacer
```

`procesar.py` es incremental: lee `DIM_TRIAGE`, descarta las notas cuyo `OID` ya está
escrito y añade solo las nuevas, así que se puede lanzar tantas veces como haga falta.
Cuántas trae cada corrida lo fija `LIMITE_REGISTROS` (hoy 5.000; `None` para la tabla
entera) y `--limite` lo pisa para una corrida concreta sin tocar el archivo.

Después de añadir notas nuevas hay que vectorizarlas:

```
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

`embedding/` deduplica por el hash del texto, de modo que solo vectoriza lo que no tiene
vector todavía: no hace falta `--rehacer` salvo que cambie el modelo de embeddings.

## 4. Errores conocidos y su solución

De `ESTADO.md` §5, más lo confirmado al preparar este documento (2026-09-16):

| Error | Causa | Solución / estado |
|---|---|---|
| `reparacion/reparar.py` escribe con pandas (`QUOTE_MINIMAL`); `procesar.py` con `nucleo/salida.py` (`QUOTE_ALL`) | dos escritores de CSV distintos | pendiente, E0.4 |
| La copia `triage_limpio.previo-<sello>.csv` no la purga `salida.rotar()` | el glob de `rotar()` no reconoce ese patrón de nombre | pendiente, E0.4 |
| `embedding/corpus.py` lee el CSV sin `encoding=` | funciona hoy por el manejo del BOM de pandas, pero es frágil | anotado para revisar en E7.2 |
| `embedding/estructurar.py` falla con `AttributeError: module 'embedding.rutas' has no attribute 'CATALOGO_SINTOMAS'` | `embedding/extraccion.py:61,64` importa `embedding.rutas` en vez de `NLP.rutas`, que es quien define esa constante | sin solución todavía; no ejecutar `embedding.estructurar` (ver `FLUJO.md` §10, discrepancia 1) |
| La receta que imprime `requisitos.py` para `clasificador_frases` es `python -m NLP.reduccion.frases` | ese comando regenera `datos/frases_etiquetadas.csv` (curado a mano) y destruye la curación | **no seguir esa receta**; usar `from NLP.reduccion import frases; frases.entrenar()` (sección 5) |
| `perdio_motivo` cuenta `dada`, `salud`, `toma`, `signos` como terminología clínica | están en el léxico curado aunque no aportan motivo de consulta en la mayoría de sus usos | ruido conocido; se revisa por término con `reparacion.revision --termino <palabra>` |
| `requirements.txt` fija `scikit-learn==1.4.2`; el `.venv` puede traer otra versión | desalineación entre archivo fijado y entorno instalado | comprobar con `pip show scikit-learn` tras instalar |
| Léxico curado sin cobertura de cola larga (`ginecobstetricia`, `tensionales`) | recursos léxicos incompletos | pendiente, E3 |
| `alarmas.reiniciar()` nunca se invoca desde `procesar.py` ni `reparar.py` | los contadores de vetos y abstenciones acumulan entre corridas dentro del mismo proceso | pendiente, E2.0; si se corre `procesar.main()` dos veces en el mismo proceso Python (p. ej. en una prueba), los contadores del resumen se mezclan |
| `evaluacion/referencia.py` falla con `FileNotFoundError` | `salidas/muestra_revision.csv` nunca se generó (`escaneo.py --muestra`) | pendiente, E0.6 |
| `NLP/tests/` sin pruebas | E2.1 no ejecutado | ver sección 3.8 |
| No existe `NLP/evaluacion/metricas.py` | E2.2 no ejecutado | `python -m NLP.evaluacion.metricas` no es un comando válido todavía |
| **`recursos/lexico.py` y `recursos/casing.py` no usan `argparse`** | cualquier invocación con `python -m`, **incluida una con `--help`**, ejecuta `main()` completo y sobrescribe el artefacto correspondiente en `salidas/`; `casing.py` además abre una conexión a la base de datos y lee la tabla completa | comprobado el 2026-09-16 al intentar listar la ayuda de todos los módulos de `recursos/`: `lexico.py` reconstruyó `lexico_clinico.json` (32.315 formas, idéntico al documentado) y `casing.py` reconstruyó `lexico_casing.json` leyendo 94.226 notas de la base de datos (4.845 entradas: 145 siglas, 164 nombres propios — antes 4.843, la diferencia es el crecimiento normal del corpus entre el 15 y el 16 de septiembre, de 94.136 a 94.226 notas). **No invocar estos dos módulos salvo que se quiera regenerar el artefacto a propósito**; no tienen forma segura de "solo consultar" |

## 5. Advertencia grande: `python -m NLP.reduccion.frases`

**No ejecutar nunca `python -m NLP.reduccion.frases`.** Su función `main()`
llama a `construir_datos()`, que **regenera `datos/frases_etiquetadas.csv` desde
las reglas y sobrescribe la curación manual** que es la fuente de verdad del
clasificador de tramos. Es el mismo error que ya ocurrió una vez con este
archivo (lección registrada en `PLAN.md` §5.7 y en el briefing de este ítem).

Para reentrenar el clasificador con los datos curados que ya existen:

```python
from NLP.reduccion import frases
frases.entrenar()
```

Esto sí es seguro: lee `datos/frases_etiquetadas.csv` tal como está y escribe
`salidas/clasificador_frases.joblib`. La única vez que se justifica
`construir_datos()` (y por tanto el `main()` completo) es para arrancar el
archivo curado **desde cero**, con la curación humana ya perdida a propósito —
nunca en una corrida normal ni en una reparación.

Esta misma advertencia aplica, con menos gravedad, a `recursos/lexico.py` y
`recursos/casing.py` (sección 4): no destruyen datos curados a mano, pero
sobrescriben artefactos generados sin previo aviso ante cualquier invocación,
incluida `--help`.

## 6. Política de versión del corrector (E7.2)

Al cambiar cualquier cosa que afecte el resultado de la fase 2 (un umbral, un
léxico nuevo, una capa nueva tras su bandera — principio 8, `PLAN.md` §3):

1. Subir `VERSION_CORRECTOR` en `procesar.py:162` (hoy
   `"4-con-spacy-y-coherencia"`). La clave de caché incluye esta cadena
   (`nucleo/cache.py`, vía `procesar.clave_cache`), así que subirla invalida por
   sí sola toda la caché anterior sin necesidad de borrar nada a mano.
2. Reparar el CSV vigente con la versión nueva:
   `python -m NLP.reparacion.reparar` (sección 3.3), revisando el informe
   (sección 3.4) antes de aplicar.
3. Aplicar solo si `recupero_motivo > perdio_motivo` y cero términos con
   veredicto real: `python -m NLP.reparacion.reparar --aplicar` (sección 3.5).
4. Revectorizar: `python -m embedding.vectorizar` (sección 3.6). No hace falta
   `--rehacer`: la deduplicación por hash de texto revectoriza solo lo que
   cambió.
5. Purgar las copias previas que ya no hagan falta
   (`triage_limpio.previo-<sello>.csv`, que `rotar()` no purga automáticamente —
   error conocido, sección 4) y los vectores huérfanos de `embedding/salidas/
   vectores.f32` si el espacio en disco lo justifica (no hay comando dedicado
   para esto último; requiere reconstruir el almacén desde cero con
   `--rehacer` si se quiere recuperar el espacio).
6. Validar: `python -m clustering --validar` (sección 3.7), comparando contra la
   última cifra de truncaciones conocida (10 de 5.020 textos, `PLAN.md` §7).

Este procedimiento no se ha ejecutado todavía de punta a punta en esta sesión
(E7.2 sigue pendiente en `ESTADO.md`); lo que aquí se documenta es el
procedimiento tal como lo describen el código y `PLAN.md` §8, no una ejecución
verificada.

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | E1.4 | Primera versión: instalación, tabla de artefactos, comandos por escenario, errores conocidos, advertencia sobre `frases.py` y sobre `recursos/lexico.py`/`recursos/casing.py`, política de versión del corrector |
